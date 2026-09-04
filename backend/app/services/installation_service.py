"""รอยเท้าของเครื่องติดตั้ง และบัญชีการย้ายสคีมา

ลูกค้าส่วนใหญ่เริ่มจาก iVS รุ่น Free แล้วค่อยขยับไป Pro หรือ Enterprise
ระหว่างทางลูกค้าจะแก้ระบบเองด้วย AI ซึ่งเป็นสิ่งที่ iVS ชวนให้ทำมาตั้งแต่ต้น
ตอนย้ายรุ่นจึงไม่ได้มีแค่สคีมาที่เคลื่อน แต่มีสามอย่างเคลื่อนพร้อมกัน:

    ข้อมูล   ตารางเพิ่มคอลัมน์
    โค้ด     ลูกค้าแก้ไปเท่าไรไม่มีใครรู้
    แอป      คอนเทนเนอร์ที่รันอยู่จริงบนเครื่อง

โมดูลนี้รับผิดชอบสองอย่างแรกของสี่ชั้นในแผน — ตัวตนของเครื่อง กับบัญชีของ
migration ที่ลงไปแล้ว ทั้งคู่ต้องอยู่ในรุ่น Free ไม่ใช่รุ่นที่ขาย เพราะรอยเท้า
ย้อนหลังสร้างไม่ได้ เครื่องที่ติดตั้งวันนี้โดยไม่มีบันทึกพวกนี้จะไม่มีวันบอกได้
ว่าสภาพเดิมของมันเป็นอย่างไร และนั่นคือเครื่องที่อัปเกรดสะอาดไม่ได้ตลอดไป

ดู docs/iVS_Edition_Migration_Design.md
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal
from app import variants
from app.models import App, Installation, SchemaMigration

logger = logging.getLogger(__name__)


class InstallationMismatch(RuntimeError):
    """ค่าตั้งค่าปัจจุบันขัดกับที่เครื่องนี้จดไว้ตอนติดตั้ง

    ไม่ใช่ข้อผิดพลาดที่ควรข้ามไป — เดินต่อแล้วข้อมูลหายเงียบ ๆ
    """


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# ตัวตนของเครื่อง
# --------------------------------------------------------------------------- #

def ensure_installation(db: Session) -> Installation:
    """คืนแถวตัวตนของเครื่องนี้ สร้างให้ถ้ายังไม่มี

    เครื่องที่รัน iVS มาก่อนหน้านี้จะยังไม่มีแถว การสร้างครั้งแรกจึงต้องรับค่า
    ที่ใช้อยู่จริงเป็นค่าตั้งต้น ไม่ใช่ค่าที่เราคิดว่าถูก — ถ้าเครื่องนั้นรันด้วย
    คำนำหน้าอื่นมาตลอด การจดค่าตามอุดมคติจะทำให้ด่านตอนบูตเตือนผิดทันที
    """
    row = db.query(Installation).filter(Installation.id == 1).first()
    if row:
        return row

    row = Installation(
        id=1,
        install_id=str(uuid.uuid4()),
        installed_at=_now(),
        installed_version=settings.APP_VERSION,
        container_prefix=settings.CONTAINER_PREFIX,
        port_range_start=settings.APP_PORT_RANGE_START,
        port_range_end=settings.APP_PORT_RANGE_END,
        docker_network=settings.DOCKER_NETWORK,
        edition="FREE",
        variant=settings.IVS_VARIANT,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "Installation recorded: id=%s prefix=%s ports=%s-%s",
        row.install_id[:8], row.container_prefix,
        row.port_range_start, row.port_range_end,
    )
    return row


def verify_installation(db: Session) -> List[str]:
    """เทียบค่าตั้งค่าปัจจุบันกับที่จดไว้ คืนรายการปัญหาที่ร้ายแรงพอให้หยุดบูต

    แยกความร้ายแรงสองระดับ:

    หยุดบูต — คำนำหน้าคอนเทนเนอร์ และเครือข่าย Docker สองค่านี้เป็นตัวที่ใช้
    "ค้นหา" ของที่รันอยู่ ถ้าเปลี่ยน ระบบจะมองไม่เห็นแอปเดิมแล้วปฏิบัติกับมัน
    เหมือนไม่มีอยู่ ซึ่งจบลงด้วยการดีพลอยซ้อนทับของจริง

    เตือนอย่างเดียว — ช่วงพอร์ต การขยายช่วงไม่เป็นอันตราย แต่การหดจนแอปที่รัน
    อยู่ตกนอกช่วงเป็นอันตราย จึงตรวจจากพอร์ตที่ใช้จริง ไม่ใช่จากตัวเลขช่วง
    """
    row = db.query(Installation).filter(Installation.id == 1).first()
    if not row:
        return []

    fatal: List[str] = []

    if row.container_prefix != settings.CONTAINER_PREFIX:
        n = db.query(App).count()
        fatal.append(
            f"เครื่องนี้ติดตั้งไว้ด้วยคำนำหน้าคอนเทนเนอร์ "
            f"{row.container_prefix!r} แต่ค่าปัจจุบันคือ "
            f"{settings.CONTAINER_PREFIX!r}\n"
            f"    ถ้าเดินต่อ แอปที่ลงทะเบียนไว้ {n} ตัวจะหายจากหน้าจอทั้งที่ยัง "
            f"ทำงานอยู่ และการดีพลอยครั้งถัดไปจะสร้างทับของเดิม\n"
            f"    แก้ CONTAINER_PREFIX ใน .env กลับเป็น {row.container_prefix!r} "
            f"แล้วเริ่มใหม่"
        )

    if row.docker_network != settings.DOCKER_NETWORK:
        fatal.append(
            f"เครื่องนี้ติดตั้งไว้บนเครือข่าย Docker {row.docker_network!r} "
            f"แต่ค่าปัจจุบันคือ {settings.DOCKER_NETWORK!r}\n"
            f"    แอปที่รันอยู่จะคุยกันข้ามเครือข่ายไม่ได้\n"
            f"    แก้ DOCKER_NETWORK ใน .env กลับเป็น {row.docker_network!r}"
        )

    # ช่วงพอร์ต: อันตรายเฉพาะตอนที่แอปจริงตกนอกช่วงใหม่
    lo, hi = settings.APP_PORT_RANGE_START, settings.APP_PORT_RANGE_END
    if (lo, hi) != (row.port_range_start, row.port_range_end):
        outside = (
            db.query(App)
            .filter(App.port.isnot(None))
            .filter((App.port < lo) | (App.port > hi))
            .count()
        )
        msg = (
            f"ช่วงพอร์ตเปลี่ยนจาก {row.port_range_start}-{row.port_range_end} "
            f"เป็น {lo}-{hi}"
        )
        if outside:
            fatal.append(
                msg + f"\n    แอป {outside} ตัวใช้พอร์ตนอกช่วงใหม่ "
                f"— จะจัดการต่อไม่ได้"
            )
        else:
            logger.warning("Installation: %s (ไม่มีแอปตกนอกช่วง)", msg)

    return fatal


def guard_or_die(db: Session) -> Installation:
    """สร้างตัวตนถ้ายังไม่มี แล้วยืนยันว่าค่าปัจจุบันยังตรงกัน

    ตั้งใจให้โยนออกมาแล้วบูตล้มเหลว การปล่อยให้บูตผ่านโดยมีคำเตือนในล็อกไม่พอ
    เพราะไม่มีใครอ่านล็อกตอนบูตสำเร็จ และความเสียหายที่กันอยู่นี้กู้คืนไม่ได้
    """
    row = ensure_installation(db)
    problems = verify_installation(db)
    if problems:
        body = "\n\n".join(f"  • {p}" for p in problems)
        raise InstallationMismatch(
            "\n\niVS หยุดทำงานเพื่อป้องกันข้อมูลสูญหาย\n\n"
            + body
            + f"\n\n  install_id: {row.install_id}\n"
        )
    return row


def set_variant(db: Session, variant: str) -> Installation:
    """บันทึกว่ากล่องนี้เปลี่ยนรุ่นย่อยเมื่อไร

    ไม่ลบข้อมูลของโมดูลที่ถูกปิด ด้วยเหตุผลเดียวกับที่การลดระดับใบอนุญาตไม่ลบ
    ตารางของ Pro — ทะเบียนที่หายไปเพราะเปลี่ยนแพ็กเกจคือทะเบียนที่ใช้เป็น
    หลักฐานไม่ได้ และหน้าที่ตาม PDPA ไม่ได้ผูกกับสิ่งที่ลูกค้าเลือกซื้อ
    """
    row = ensure_installation(db)
    if row.variant != variant:
        row.variant = variant
        row.variant_changed_at = _now()
        db.commit()
        logger.info("Installation variant -> %s", variant)
    return row


def set_edition(db: Session, edition: str) -> Installation:
    """บันทึกว่าเครื่องนี้เปลี่ยนรุ่นเมื่อไร — ไม่แตะค่าที่ผูกกับเครื่อง"""
    row = ensure_installation(db)
    if row.edition != edition:
        row.edition = edition
        row.edition_changed_at = _now()
        db.commit()
        logger.info("Installation edition -> %s", edition)
    return row


# --------------------------------------------------------------------------- #
# บัญชี migration
# --------------------------------------------------------------------------- #

def applied_ids(db: Session) -> set:
    return {
        m.migration_id
        for m in db.query(SchemaMigration).filter(SchemaMigration.ok.is_(True)).all()
    }


def is_applied(db: Session, migration_id: str) -> bool:
    return (
        db.query(SchemaMigration)
        .filter(SchemaMigration.migration_id == migration_id)
        .filter(SchemaMigration.ok.is_(True))
        .first()
        is not None
    )


def checksum_of(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(
    db: Session,
    migration_id: str,
    *,
    checksum: str = "",
    duration_ms: int = 0,
    ok: bool = True,
    error: str = "",
) -> None:
    """จดว่า migration หนึ่งลงแล้ว — แถวเดิมไม่ถูกลบ ถูกเขียนทับเฉพาะผลลัพธ์

    แถวที่เคยล้มเหลวแล้วสำเร็จทีหลังต้องเหลือร่องรอยว่าเคยล้ม จึงเก็บข้อความ
    ผิดพลาดเดิมไว้ต่อท้าย แทนที่จะลบทิ้งเมื่อรอบใหม่ผ่าน
    """
    row = (
        db.query(SchemaMigration)
        .filter(SchemaMigration.migration_id == migration_id)
        .first()
    )
    if row:
        if not row.ok and ok:
            row.error = (row.error or "") + "\n[ผ่านในรอบถัดมา]"
        row.ok = ok
        row.applied_at = _now()
        row.duration_ms = duration_ms
        row.checksum = checksum or row.checksum
        if error:
            row.error = error
    else:
        db.add(
            SchemaMigration(
                migration_id=migration_id,
                edition=_current_edition(db),
                app_version=settings.APP_VERSION,
                applied_at=_now(),
                duration_ms=duration_ms,
                checksum=checksum,
                ok=ok,
                error=error,
            )
        )
    db.commit()


def _current_edition(db: Session) -> str:
    row = db.query(Installation).filter(Installation.id == 1).first()
    return row.edition if row else "FREE"


def run_step(db: Session, migration_id: str, fn: Callable[[], None],
             *, checksum: str = "") -> bool:
    """รัน migration หนึ่งขั้นถ้ายังไม่เคยลง แล้วจดผล

    คืน True เมื่อขั้นนี้ถูกรันในรอบนี้จริง — ไม่ใช่เมื่อสำเร็จ ผู้เรียกที่อยาก
    รู้ว่าสำเร็จไหมให้ดูที่บัญชี เพราะความล้มเหลวถูกจดไว้แล้วและไม่ควรทำให้บูต
    ทั้งเครื่องล้ม การย้ายสคีมาที่พลาดหนึ่งขั้นยังดีกว่าเครื่องที่เปิดไม่ขึ้น
    """
    if is_applied(db, migration_id):
        return False

    started = _now()
    try:
        fn()
        ms = int((_now() - started).total_seconds() * 1000)
        record(db, migration_id, checksum=checksum, duration_ms=ms, ok=True)
        logger.info("Migration %s applied in %dms", migration_id, ms)
    except Exception as e:                       # noqa: BLE001 — จดแล้วเดินต่อ
        ms = int((_now() - started).total_seconds() * 1000)
        record(db, migration_id, checksum=checksum, duration_ms=ms,
               ok=False, error=str(e)[:2000])
        logger.error("Migration %s failed: %s", migration_id, e)
    return True


def summary(db: Session) -> dict:
    """สรุปรอยเท้าของเครื่องนี้ — ใช้ทั้งในหน้าจอและในรายงานก่อนอัปเกรด"""
    row = ensure_installation(db)
    migrations = (
        db.query(SchemaMigration).order_by(SchemaMigration.id.asc()).all()
    )
    failed = [m.migration_id for m in migrations if not m.ok]
    return {
        "install_id": row.install_id,
        "installed_at": row.installed_at.isoformat() if row.installed_at else None,
        "installed_version": row.installed_version,
        "current_version": settings.APP_VERSION,
        "edition": row.edition,
        "edition_changed_at": (
            row.edition_changed_at.isoformat() if row.edition_changed_at else None
        ),
        "variant": row.variant or "base",
        "variant_configured": settings.IVS_VARIANT,
        # รุ่นย่อยที่ตั้งค่าไว้ต่างจากที่จด ไม่ใช่เรื่องต้องหยุดบูต การเปลี่ยน
        # รุ่นย่อยแค่ซ่อนหรือเปิดเมนู ไม่ได้ทำให้ข้อมูลหาย ต่างจากคำนำหน้า
        # คอนเทนเนอร์ แต่ต้องเห็นในรายงาน เพราะเมนูที่หายไปเงียบ ๆ ทำให้คนคิดว่า
        # การอัปเกรดลบของเขา
        "variant_drifted": (row.variant or "base") != settings.IVS_VARIANT,
        "modules": variants.summary(
            settings.IVS_VARIANT, row.edition or "FREE"
        )["modules"],
        "container_prefix": row.container_prefix,
        "port_range": [row.port_range_start, row.port_range_end],
        "docker_network": row.docker_network,
        "migrations_applied": len([m for m in migrations if m.ok]),
        "migrations_failed": failed,
        "latest_migration": migrations[-1].migration_id if migrations else None,
    }
