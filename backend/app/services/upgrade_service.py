"""รายงานก่อนอัปเกรด — สิ่งที่ลูกค้าต้องเห็นก่อนกด ไม่ใช่หลังจากพัง

ชั้นสุดท้ายของรอยเท้า สามชั้นแรกเก็บข้อเท็จจริงเอาไว้ ชั้นนี้เอามาเรียงให้คน
ตัดสินใจได้ในหน้าจอเดียว

ทำไมต้องตรวจก่อนโดยไม่แตะอะไร: การอัปเกรดที่เริ่มแล้วหยุดกลางทางเป็นสภาพที่แย่
ที่สุด — สคีมาไปครึ่งทาง ไฟล์ไปครึ่งทาง และไม่มีใครรู้ว่าครึ่งไหน การตรวจที่
อ่านอย่างเดียวจึงต้องจบก่อนเสมอ แล้วให้คนเป็นคนกด

blockers กับ warnings ต่างกันตรงที่ blockers ต้องมีคนตอบก่อน ส่วน warnings แค่
ต้องอ่าน สิ่งที่ทำให้ข้อมูลหายเป็น blocker เสมอ ไม่มีข้อยกเว้น

ดู docs/iVS_Edition_Migration_Design.md
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import App, AppPdpa, AuditLog, UpgradeSnapshot, VaultKey
from app.services import baseline_service, custom_loader, installation_service

logger = logging.getLogger(__name__)

# ลำดับรุ่น — ใช้ตัดสินว่าเป็นการขึ้นหรือลง
_ORDER = ["FREE", "LITE", "STD", "PRO", "ENT"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rank(edition: str) -> int:
    try:
        return _ORDER.index(edition.upper())
    except ValueError:
        return -1


def _counts(db: Session) -> dict:
    """ตัวเลขที่ต้องเท่ากันก่อนและหลัง

    เลือกเฉพาะของที่ลดลงแล้วแปลว่าเสียหาย ไม่ใช่ทุกตาราง บันทึกตรวจสอบเพิ่มขึ้น
    ได้ตลอดเวลาเพราะการอัปเกรดเองก็เขียนบันทึก จึงเทียบแบบ "ต้องไม่ลด" ไม่ใช่
    "ต้องเท่าเดิม"
    """
    return {
        "apps": db.query(App).count(),
        "ropa": db.query(AppPdpa).count(),
        "audit_logs": db.query(AuditLog).count(),
        "vault_keys": db.query(VaultKey).count(),
    }


def _containers() -> List[dict]:
    """คอนเทนเนอร์ที่รันอยู่จริง ณ ตอนนี้ — อ่านจาก Docker ไม่ใช่จากฐานข้อมูล

    ฐานข้อมูลบอกว่าควรมีอะไร Docker บอกว่ามีอะไรจริง ตอนอัปเกรดต้องใช้อันหลัง
    เพราะสิ่งที่จะเสียหายคือของจริง ไม่ใช่แถวในตาราง
    """
    try:
        from app.services.docker_service import docker_service
        if not docker_service.is_available():
            return []
        prefix = settings.CONTAINER_PREFIX
        out = []
        for c in docker_service.client.containers.list(all=True):
            if not c.name.startswith(prefix):
                continue
            ports = []
            try:
                for _, binds in (c.attrs.get("NetworkSettings", {}).get("Ports") or {}).items():
                    for b in binds or []:
                        ports.append(b.get("HostPort"))
            except Exception:                      # noqa: BLE001
                pass
            out.append({"name": c.name, "status": c.status, "ports": ports})
        return out
    except Exception as e:                         # noqa: BLE001
        logger.warning("อ่านรายการคอนเทนเนอร์ไม่ได้: %s", e)
        return []


def preflight(db: Session, to_edition: Optional[str] = None) -> dict:
    """ตรวจก่อนอัปเกรด อ่านอย่างเดียว ไม่เปลี่ยนอะไรบนเครื่อง

    คืนรายงานเต็ม พร้อม blockers ที่ต้องเคลียร์ก่อน และ warnings ที่ต้องอ่าน
    """
    inst = installation_service.ensure_installation(db)
    from_edition = inst.edition
    to_edition = (to_edition or from_edition).upper()

    blockers: List[dict] = []
    warnings: List[dict] = []

    # ── ตัวตนของเครื่อง — เรื่องที่ทำให้แอปหายทั้งชุด ──
    for problem in installation_service.verify_installation(db):
        blockers.append({"kind": "installation", "detail": problem})

    # ── บัญชี migration ที่ยังค้างอยู่ ──
    footprint = installation_service.summary(db)
    if footprint["migrations_failed"]:
        blockers.append({
            "kind": "migration_failed",
            "detail": (
                "มี migration ที่ลงไม่สำเร็จค้างอยู่: "
                + ", ".join(footprint["migrations_failed"])
                + " — อัปเกรดทับสภาพที่ยังไม่นิ่งจะทำให้หาต้นเหตุไม่เจอ"
            ),
        })

    # ── โค้ดที่ลูกค้าแก้ ──
    d = baseline_service.drift(db)
    if not d.get("available"):
        warnings.append({
            "kind": "no_baseline",
            "detail": "ยังไม่มีฐานลายนิ้วมือ — บอกไม่ได้ว่ามีไฟล์แกนถูกแก้หรือไม่",
        })
    else:
        if not d["trustworthy"]:
            warnings.append({"kind": "weak_baseline", "detail": d["caveat"]})
        if d["core_conflicts"]:
            blockers.append({
                "kind": "core_modified",
                "detail": (
                    f"ไฟล์ในเขตแกน {len(d['core_conflicts'])} ไฟล์ถูกแก้ "
                    "การอัปเกรดจะเขียนทับ ต้องเลือกก่อนว่าจะเก็บของใคร"
                ),
                "files": [f["path"] for f in d["core_conflicts"]],
            })
        if d["gray_conflicts"]:
            warnings.append({
                "kind": "gray_modified",
                "detail": (
                    f"ไฟล์ตั้งค่า/ธีม {len(d['gray_conflicts'])} ไฟล์ถูกแก้ "
                    "ต้องรวมด้วยมือหลังอัปเกรด"
                ),
                "files": [f["path"] for f in d["gray_conflicts"]],
            })

    # ── เขตของลูกค้า ──
    zone = custom_loader.load_report()
    if not zone["healthy"]:
        warnings.append({
            "kind": "custom_zone_unhealthy",
            "detail": (
                "มีของในเขตลูกค้าที่โหลดไม่ขึ้นอยู่แล้วก่อนอัปเกรด: "
                + ", ".join(zone["failures"])
                + " — แก้ก่อนจะได้แยกออกว่าอันไหนพังเพราะอัปเกรด"
            ),
        })

    # ── รุ่นย่อย ──
    if footprint.get("variant_drifted"):
        warnings.append({
            "kind": "variant_changed",
            "detail": (
                f"รุ่นย่อยที่ตั้งค่าไว้ ({footprint['variant_configured']}) "
                f"ต่างจากที่กล่องนี้จดไว้ ({footprint['variant']}) "
                "เมนูบางอย่างจะหายไปหรือโผล่ขึ้นมา ข้อมูลของโมดูลที่ถูกปิดยังอยู่ครบ"
            ),
        })

    # ── ทิศทางของรุ่น ──
    if _rank(to_edition) < _rank(from_edition):
        warnings.append({
            "kind": "downgrade",
            "detail": (
                f"เป็นการลดรุ่นจาก {from_edition} เป็น {to_edition} "
                "ฟีเจอร์จะถูกปิด แต่ข้อมูลและตารางทั้งหมดยังอยู่และส่งออกได้ "
                "หน้าที่ตาม PDPA ไม่ได้หยุดตามใบอนุญาต"
            ),
        })

    containers = _containers()

    return {
        "from": {"edition": from_edition, "version": inst.installed_version or settings.APP_VERSION},
        "to": {"edition": to_edition, "version": settings.APP_VERSION},
        "installation": footprint,
        "counts": _counts(db),
        "containers": {
            "total": len(containers),
            "running": len([c for c in containers if c["status"] == "running"]),
            "list": containers,
            # แอปไม่ถูกแตะระหว่างอัปเกรดแกน เพราะเป็นคนละคอนเทนเนอร์ ประโยคนี้
            # ต้องขึ้นในรายงาน เพราะคำถามแรกของทุกคนคือ "ของที่รันอยู่จะดับไหม"
            "untouched": True,
        },
        "drift": d,
        "custom_zone": zone,
        "blockers": blockers,
        "warnings": warnings,
        "can_proceed": not blockers,
        "checked_at": _now().isoformat(),
    }


def save_snapshot(db: Session, report: dict, user_id: Optional[int] = None,
                  backup_db: bool = True) -> UpgradeSnapshot:
    """เก็บรายงานและสำเนาฐานข้อมูลไว้ก่อนเริ่มอัปเกรดจริง

    สำรองด้วยการคัดลอกไฟล์ ไม่ใช่ dump เพราะการกู้คืนต้องง่ายพอที่คนตกใจจะทำได้
    ถูกในเวลาตี 2 — คัดลอกไฟล์กลับที่เดิมแล้วเริ่มใหม่ จบ
    """
    path = ""
    if backup_db:
        url = settings.DATABASE_URL
        if url.startswith("sqlite:///"):
            src = Path(url.replace("sqlite:///", "", 1))
            if not src.is_absolute():
                src = Path.cwd() / src
            if src.is_file():
                stamp = _now().strftime("%Y%m%d_%H%M%S")
                dst = src.with_name(f"{src.stem}.before-upgrade-{stamp}{src.suffix}")
                try:
                    shutil.copy2(src, dst)
                    path = str(dst)
                    logger.info("DB backed up to %s", dst)
                except OSError as e:
                    logger.error("สำรองฐานข้อมูลไม่สำเร็จ: %s", e)

    row = UpgradeSnapshot(
        from_edition=report["from"]["edition"],
        to_edition=report["to"]["edition"],
        from_version=report["from"]["version"],
        to_version=report["to"]["version"],
        started_at=_now(),
        outcome="preflight",
        db_backup_path=path,
        containers=json.dumps(report["containers"]["list"], ensure_ascii=False),
        report=json.dumps(report, ensure_ascii=False),
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def verify_after(db: Session, snapshot: UpgradeSnapshot) -> dict:
    """เทียบตัวเลขหลังอัปเกรดกับที่บันทึกไว้ก่อน

    ROPA ลดลงคือเหตุให้ถอยทันที ไม่ต้องถาม กฎของ iVS คือทะเบียนนั้นไม่ลบ ไม่ล้าง
    ไม่เรียงใหม่ เพราะ PDPA ไม่ได้สั่งให้ลบ และทะเบียนที่ลดลงได้คือทะเบียนที่ใช้
    เป็นหลักฐานไม่ได้
    """
    try:
        before = json.loads(snapshot.report or "{}").get("counts") or {}
    except Exception:                              # noqa: BLE001
        before = {}
    after = _counts(db)

    losses = []
    for key, was in before.items():
        now = after.get(key, 0)
        if now < was:
            losses.append({"what": key, "before": was, "after": now})

    return {
        "before": before,
        "after": after,
        "losses": losses,
        "ok": not losses,
        "must_roll_back": any(l["what"] == "ropa" for l in losses),
    }
