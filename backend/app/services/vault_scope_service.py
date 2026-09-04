"""ขอบเขตของคลังกุญแจ — ปฏิเสธไว้ก่อน ให้เท่าที่จำเป็น

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

สิ่งที่แก้
---------
เดิม deploy ทุกครั้งทำแบบนี้:

    vault_keys = db.query(VaultKey).all()
    injected_env = vault_service.build_env_dict(vault_keys)

กุญแจทุกใบเข้าทุกคอนเทนเนอร์ เกมสถิตถือกุญแจ OpenAI ชุดเดียวกับแอปที่เรียก AI
จริง แอปใดถูกเจาะ หรือมีใครอ่าน env ของคอนเทนเนอร์ใดได้ กุญแจหลุดทั้งชุดพร้อมกัน
และเจ้าของกุญแจไม่มีทางรู้ว่าหลุดจากทางไหน เพราะทุกทางถือเหมือนกันหมด

หลักที่ใช้
---------
**ไม่ไว้ใจใครเลย** แอปที่รันอยู่บนเครื่องเดียวกันไม่ได้แปลว่าเชื่อถือได้เท่ากัน
ความเป็นเพื่อนบ้านไม่ใช่สิทธิ์ ต้องมีคนให้ไว้ชัดเจนถึงจะได้

**ให้เท่าที่จำเป็น** สิทธิ์เริ่มต้นคือไม่มี ไม่มีแถวที่ตรง = ไม่ได้กุญแจ ไม่มี
โหมด "เปิดหมดไว้ก่อนแล้วค่อยเก็บ" เพราะโหมดแบบนั้นไม่เคยถูกเก็บ

สามแกนที่ตั้งได้
---------------
1. **ตัวตน** — กุญแจใบนี้ให้แอปไหนบ้าง (`VaultGrant.app_id`)
2. **เส้นทาง/กลุ่ม** — จัดกุญแจเป็น namespace แล้วให้สิทธิ์ทีละกลุ่ม
   (`VaultKey.namespace`) การให้ตามรูปแบบจะถูกกางเป็นแถวจริงทันที ไม่เก็บเป็น
   ไวลด์การ์ดไว้ตีความตอนรัน — คำถามว่าใครถือกุญแจใบนี้ต้องตอบได้ด้วยการอ่านตาราง
3. **ความสามารถ** — ทำอะไรได้กับกุญแจใบนั้น (`VaultCapability`)
   ฝั่งแอปมีได้อย่างเดียวคือ inject ส่วน reveal และ rotate เป็นการกระทำของคน
   `VaultKey.allow_reveal=False` ทำให้กุญแจใส่เข้าคอนเทนเนอร์ได้แต่ไม่มีใคร
   คัดลอกค่าออกไปได้ แม้แต่ผู้ดูแลระบบ

สิ่งที่โมดูลนี้ไม่ทำ
------------------
ไม่ยกสิทธิ์ย้อนหลังให้แอปที่เคยได้กุญแจมาก่อน การสร้างสิทธิ์ให้อัตโนมัติเท่ากับ
เขียนช่องโหว่เดิมลงเป็นข้อมูล แล้วอ้างว่าปิดแล้ว แอปที่เคยพึ่งกุญแจต้องได้รับ
สิทธิ์ใหม่โดยมีคนกด และมีชื่อคนนั้นอยู่ในแถว
"""
from __future__ import annotations

import fnmatch
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.models import App, User, VaultCapability, VaultGrant, VaultKey
from app.services.vault_service import vault_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ชื่อตัวแปรสภาพแวดล้อมที่เชลล์และภาษาโปรแกรมส่วนใหญ่ยอมรับ
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def derived_env_name(key: VaultKey) -> str:
    """ชื่อที่ระบบสร้างให้จากผู้ให้บริการและชื่อกุญแจ"""
    return f"{key.provider.upper()}_{key.name.upper().replace(' ', '_')}"


def env_name(key: VaultKey) -> str:
    """ชื่อตัวแปรที่กุญแจใบนี้จะกลายเป็นในคอนเทนเนอร์

    ใช้ชื่อที่ตั้งเองก่อนเสมอ ถ้าไม่ได้ตั้งจึงกลับไปใช้ชื่อที่สร้างจากผู้ให้บริการ
    """
    override = (getattr(key, "env_override", "") or "").strip()
    return override or derived_env_name(key)


def grant_env_name(key: VaultKey, grant: Optional[VaultGrant]) -> str:
    """ชื่อตัวแปรที่กุญแจใบนี้จะกลายเป็น *ในแอปที่ได้รับสิทธิ์บรรทัดนี้*

    ลำดับ: ชื่อของสิทธิ์ → ชื่อของกุญแจ → ชื่อที่สร้างจากผู้ให้บริการ

    ความลับที่สองระบบใช้ร่วมกันมักถูกอ่านคนละชื่อที่ปลายทางแต่ละฝั่ง ถ้าชื่อผูก
    อยู่กับกุญแจอย่างเดียว ทางออกเดียวคือทำกุญแจสองใบใส่ค่าเดียวกัน แล้ววันหนึ่ง
    จะหมุนใบเดียวแล้วอีกใบค้าง — ระบบสองฝั่งถือความลับคนละค่าโดยไม่มีใครรู้
    """
    if grant is not None:
        override = (getattr(grant, "env_override", "") or "").strip()
        if override:
            return override
    return env_name(key)


def env_name_valid(name: str) -> bool:
    """ชื่อนี้ใช้เป็นตัวแปรสภาพแวดล้อมได้จริงหรือไม่

    ชื่อที่มี :// ช่องว่าง หรือขีดกลาง ตั้งเป็นตัวแปรได้ในบางเชลล์แต่โปรแกรม
    อ่านไม่ได้ตามปกติ — กุญแจที่ชื่อแบบนั้นถูกส่งเข้าคอนเทนเนอร์ไปโดยไม่มีใครใช้
    """
    return bool(_ENV_RE.match(name or ""))


def default_namespace(key: VaultKey) -> str:
    """กลุ่มเริ่มต้นจากผู้ให้บริการ ใช้เมื่อยังไม่มีใครจัดกลุ่มเอง"""
    return (key.provider or "").strip().lower().replace(" ", "-") or "ungrouped"


def namespace_of(key: VaultKey) -> str:
    return (key.namespace or "").strip() or default_namespace(key)


# --------------------------------------------------------------------------- #
# การตัดสิน
# --------------------------------------------------------------------------- #

def _active(grant: VaultGrant) -> bool:
    if grant.revoked_at:
        return False
    exp = _aware(grant.expires_at)
    return not (exp and exp <= _now())


def granted_pairs(db: Session, app_id: int,
                  capability: VaultCapability = VaultCapability.INJECT
                  ) -> List[tuple]:
    """คู่ (สิทธิ์, กุญแจ) ที่แอปนี้ถืออยู่จริง ณ ตอนนี้

    คืนสิทธิ์มาด้วย ไม่ใช่แค่กุญแจ เพราะชื่อตัวแปรอาจถูกตั้งไว้ที่สิทธิ์บรรทัดนั้น
    ถ้าโยนสิทธิ์ทิ้งตั้งแต่ตรงนี้ ชื่อที่ตั้งไว้จะหายไปเงียบ ๆ แล้วคอนเทนเนอร์
    จะได้ตัวแปรคนละชื่อกับที่โปรแกรมอ่าน
    """
    rows = [g for g in db.query(VaultGrant).filter(
        VaultGrant.app_id == app_id,
        VaultGrant.capability == capability,
        VaultGrant.revoked_at.is_(None),
    ).all() if _active(g)]
    if not rows:
        return []
    keys = {k.id: k for k in db.query(VaultKey).filter(
        VaultKey.id.in_([g.vault_key_id for g in rows])).all()}
    return [(g, keys[g.vault_key_id]) for g in rows if g.vault_key_id in keys]


def granted_keys(db: Session, app_id: int,
                 capability: VaultCapability = VaultCapability.INJECT) -> List[VaultKey]:
    """กุญแจที่แอปนี้มีสิทธิ์จริง ณ ตอนนี้ — ที่เดียวที่ตอบคำถามนี้"""
    return [k for _, k in granted_pairs(db, app_id, capability)]


def build_env(keys: Sequence[VaultKey]) -> Dict[str, str]:
    """แปลงกุญแจเป็นตัวแปร โดยเคารพชื่อที่ตั้งเอง

    ไม่เรียก vault_service.build_env_dict เพราะตัวนั้นสร้างชื่อจากผู้ให้บริการ
    เสมอ และจะข้ามชื่อที่ผู้ดูแลตั้งไว้ ซึ่งเป็นเหตุผลทั้งหมดที่ช่องนั้นมีอยู่
    """
    return build_env_for_grants([(None, k) for k in keys])


def build_env_for_grants(pairs: Sequence[tuple]) -> Dict[str, str]:
    """เหมือน build_env แต่เคารพชื่อที่ตั้งไว้ที่สิทธิ์แต่ละบรรทัดก่อน

    สองสิทธิ์ที่ชี้กุญแจใบเดียวกันแต่ตั้งชื่อต่างกัน จะได้ตัวแปรสองชื่อค่าเดียวกัน
    ซึ่งเป็นสิ่งที่ตั้งใจ — ระบบปลายทางคนละตัวอ่านชื่อคนละอย่าง
    """
    env: Dict[str, str] = {}
    for grant_row, k in pairs:
        try:
            env[grant_env_name(k, grant_row)] = vault_service.decrypt(k.encrypted_value)
        except Exception as e:
            logger.warning("ถอดรหัสกุญแจ %s ไม่สำเร็จ: %s", k.name, e)
    return env


def env_for_app(db: Session, app: App) -> Dict[str, str]:
    """ตัวแปรจากคลังที่แอปนี้ควรได้รับ

    แทนที่ `build_env_dict(db.query(VaultKey).all())` ทุกจุด แอปที่ไม่มีสิทธิ์ใด
    จะได้ dict ว่าง ซึ่งถูกต้องตามหลักปฏิเสธไว้ก่อน และถูกบันทึกไว้ให้เห็น
    """
    pairs = granted_pairs(db, app.id, VaultCapability.INJECT)
    env = build_env_for_grants(pairs)
    total = db.query(VaultKey).count()
    logger.info(
        "Vault scope: %s ได้กุญแจ %d/%d ใบ", app.slug, len(pairs), total
    )
    return env


def may_reveal(key: VaultKey) -> bool:
    """กุญแจใบนี้อนุญาตให้เปิดดูค่าจริงหรือไม่ — คนละเรื่องกับสิทธิ์ของผู้ใช้

    บทบาทตอบว่า "ใครมีสิทธิ์ขอ" ธงนี้ตอบว่า "ใบนี้ยอมให้ขอหรือเปล่า" กุญแจที่
    ตั้งเป็นใส่อย่างเดียว จะไม่มีเส้นทางใดในระบบที่คืนค่าจริงออกไปได้
    """
    return bool(getattr(key, "allow_reveal", True))


# --------------------------------------------------------------------------- #
# การให้และถอนสิทธิ์
# --------------------------------------------------------------------------- #

def grant(db: Session, key: VaultKey, app: App, user: Optional[User],
          capability: VaultCapability = VaultCapability.INJECT,
          note: str = "", expires_at: Optional[datetime] = None,
          env_override: str = "") -> VaultGrant:
    """ให้สิทธิ์หนึ่งบรรทัด — คืนแถวเดิมถ้าให้ไว้แล้ว (เรียกซ้ำได้)"""
    env_override = (env_override or "").strip()[:120]
    row = db.query(VaultGrant).filter_by(
        vault_key_id=key.id, app_id=app.id, capability=capability).first()
    if row:
        if row.revoked_at:                       # เคยถอนแล้วให้ใหม่
            row.revoked_at = None
            row.revoked_by = None
            row.granted_by = user.id if user else None
            row.granted_at = _now()
        row.note = note or row.note
        row.expires_at = expires_at
        # ส่งค่าว่างมา = ไม่ได้ตั้งใจแก้ ไม่ใช่สั่งให้ล้างชื่อเดิม
        # ล้างชื่อได้ด้วยการแก้สิทธิ์ตรง ๆ ที่ set_grant_env_name
        if env_override:
            row.env_override = env_override
        return row

    row = VaultGrant(
        vault_key_id=key.id, app_id=app.id, capability=capability,
        note=note[:2000], expires_at=expires_at, env_override=env_override,
        granted_by=user.id if user else None,
    )
    db.add(row)
    return row


def set_grant_env_name(grant_row: VaultGrant, name: str) -> VaultGrant:
    """ตั้งหรือล้างชื่อตัวแปรของสิทธิ์บรรทัดนี้ — ค่าว่างคือกลับไปใช้ชื่อของกุญแจ

    แยกจาก grant() เพราะที่นั่นค่าว่างแปลว่า "ไม่ได้แตะ" ส่วนที่นี่ค่าว่างแปลว่า
    "เอาชื่อออก" สองความหมายนี้ต่างกัน และการรวมไว้ทางเดียวจะทำให้ล้างชื่อไม่ได้
    หรือล้างโดยไม่ได้ตั้งใจ อย่างใดอย่างหนึ่งเสมอ
    """
    grant_row.env_override = (name or "").strip()[:120]
    return grant_row


def revoke(db: Session, grant_row: VaultGrant, user: Optional[User]) -> VaultGrant:
    """ถอนสิทธิ์ — เก็บแถวไว้เป็นประวัติ ไม่ลบทิ้ง

    คำถามหลังเกิดเหตุคือ "แอปนี้เคยถือกุญแจใบนั้นช่วงไหน" การลบแถวทำให้ตอบไม่ได้
    """
    if not grant_row.revoked_at:
        grant_row.revoked_at = _now()
        grant_row.revoked_by = user.id if user else None
    return grant_row


def grant_by_namespace(db: Session, pattern: str, app: App, user: Optional[User],
                       capability: VaultCapability = VaultCapability.INJECT,
                       note: str = "") -> List[VaultKey]:
    """ให้สิทธิ์ทุกใบในกลุ่มที่ตรงรูปแบบ — กางเป็นแถวจริงทันที

    เก็บรูปแบบไว้แล้วค่อยตีความตอนรัน จะทำให้กุญแจใบใหม่ที่เพิ่มเข้ากลุ่มภายหลัง
    ไหลเข้าแอปเองโดยไม่มีใครตัดสินใจ ซึ่งเป็นช่องโหว่แบบเดียวกับที่กำลังแก้อยู่
    """
    pattern = (pattern or "").strip()
    if not pattern:
        return []
    matched = [k for k in db.query(VaultKey).all()
               if fnmatch.fnmatch(namespace_of(k), pattern)]
    for k in matched:
        grant(db, k, app, user, capability=capability,
              note=note or f"ให้ตามกลุ่ม {pattern}")
    return matched


# --------------------------------------------------------------------------- #
# การแสดงผล
# --------------------------------------------------------------------------- #

def key_row(db: Session, key: VaultKey) -> Dict:
    grants = db.query(VaultGrant).filter(
        VaultGrant.vault_key_id == key.id,
        VaultGrant.revoked_at.is_(None),
    ).all()
    apps = []
    for g in grants:
        if not _active(g):
            continue
        a = db.query(App).filter(App.id == g.app_id).first()
        if a:
            per_grant = grant_env_name(key, g)
            apps.append({
                "grant_id": g.id, "app_id": a.id, "slug": a.slug, "name": a.name,
                "capability": g.capability.value if hasattr(g.capability, "value") else str(g.capability),
                "expires_at": g.expires_at.isoformat() if g.expires_at else None,
                # ชื่อที่แอปตัวนี้จะได้รับจริง อาจต่างจากชื่อของกุญแจ
                "env_name": per_grant,
                "env_overridden": bool((getattr(g, "env_override", "") or "").strip()),
                "env_valid": env_name_valid(per_grant),
            })
    return {
        "id": key.id,
        "name": key.name,
        "provider": key.provider,
        # หมวดใช้จัดกลุ่มบนหน้าแรก และแก้ได้จากหน้านี้
        "category": (key.category or "general"),
        "namespace": namespace_of(key),
        "namespace_explicit": bool((key.namespace or "").strip()),
        "env_name": env_name(key),
        "env_derived": derived_env_name(key),
        "env_overridden": bool((getattr(key, "env_override", "") or "").strip()),
        # ชื่อที่โปรแกรมอ่านไม่ได้ = กุญแจที่ส่งไปแล้วไม่มีใครใช้
        "env_valid": env_name_valid(env_name(key)),
        "allow_reveal": may_reveal(key),
        "granted_to": sorted(apps, key=lambda x: x["slug"]),
        "grant_count": len(apps),
    }


def overview(db: Session) -> Dict:
    """ภาพรวมสามแกน สำหรับหน้าจอ

    ตัวเลขที่สำคัญที่สุดคือกุญแจที่ยังไม่มีใครได้รับสิทธิ์ — ไม่ใช่ปัญหา แต่เป็น
    รายการที่ต้องตัดสินใจ และแอปที่ไม่มีกุญแจเลยทั้งที่อาจเคยใช้อยู่
    """
    keys = db.query(VaultKey).all()
    apps = db.query(App).order_by(App.name).all()
    rows = [key_row(db, k) for k in keys]

    by_ns: Dict[str, int] = {}
    for r in rows:
        by_ns[r["namespace"]] = by_ns.get(r["namespace"], 0) + 1

    app_rows = []
    for a in apps:
        got = granted_pairs(db, a.id, VaultCapability.INJECT)
        app_rows.append({
            "app_id": a.id, "slug": a.slug, "name": a.name,
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "key_count": len(got),
            # ชื่อที่คอนเทนเนอร์ตัวนี้จะเห็นจริง ไม่ใช่ชื่อกลางของกุญแจ
            "keys": sorted(grant_env_name(k, g) for g, k in got),
        })

    return {
        "keys": rows,
        "apps": app_rows,
        "namespaces": [{"namespace": k, "keys": v} for k, v in sorted(by_ns.items())],
        "totals": {
            "keys": len(rows),
            "keys_ungranted": sum(1 for r in rows if r["grant_count"] == 0),
            "keys_no_reveal": sum(1 for r in rows if not r["allow_reveal"]),
            "keys_bad_env": sum(1 for r in rows if not r["env_valid"]),
            # ชื่อที่ตั้งไว้ที่สิทธิ์ก็พังได้เหมือนกัน และนับแยกเพราะแก้คนละที่
            "grants_bad_env": sum(1 for r in rows for a in r["granted_to"]
                                  if not a["env_valid"]),
            "apps": len(app_rows),
            "apps_without_keys": sum(1 for a in app_rows if a["key_count"] == 0),
        },
    }


def diff_against_legacy(db: Session) -> Dict:
    """สิ่งที่เปลี่ยนไปเมื่อเทียบกับพฤติกรรมเดิม

    เดิมทุกแอปได้กุญแจทุกใบ ตอนนี้ได้เท่าที่มีคนให้ ตารางนี้บอกตรง ๆ ว่าแอปไหน
    จะได้กุญแจน้อยลงกี่ใบเมื่อ deploy ครั้งถัดไป เพื่อไม่ให้ความเปลี่ยนแปลงนี้
    ไปโผล่ตอนแอปพังกลางงาน
    """
    total = db.query(VaultKey).count()
    out = []
    for a in db.query(App).order_by(App.name).all():
        got = len(granted_keys(db, a.id, VaultCapability.INJECT))
        if got < total:
            out.append({
                "slug": a.slug, "name": a.name,
                "had_before": total, "has_now": got, "loses": total - got,
            })
    return {"total_keys": total, "apps": out}
