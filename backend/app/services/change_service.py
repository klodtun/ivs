"""การควบคุมการเปลี่ยนแปลง ผูกกับเวอร์ชันของแอป

ISO 13485 ข้อ 7.3.9 กำหนดว่าการเปลี่ยนแปลงการออกแบบต้องถูก **ระบุ ทบทวน
ทวนสอบ อนุมัติ** ก่อนนำไปใช้ และต้องประเมิน "ผลกระทบต่อชิ้นส่วนที่ประกอบแล้ว
และผลิตภัณฑ์ที่ส่งมอบไปแล้ว"

ข้อกำหนดนี้เป็นข้อที่ทีมซอฟต์แวร์พลาดบ่อยที่สุด ไม่ใช่เพราะไม่เข้าใจ แต่เพราะ
การเปลี่ยนแปลงในซอฟต์แวร์เกิดถี่เกินกว่าที่ใครจะจำมาบันทึกย้อนหลังได้ พอถึงวัน
ตรวจก็เหลือแต่ประวัติ git ที่ตอบไม่ได้ว่าใครทบทวน ใครอนุมัติ กระทบข้อกำหนดข้อไหน

iVS แก้ด้วยการกลับด้าน: **การ redeploy สร้างระเบียนให้เองทุกครั้ง** ในสถานะ
ร่างที่ยังไม่ประเมิน ระเบียนโผล่ในรายการช่องว่างทันที ผู้ใช้จึงไม่ต้องจำว่า
"ต้องบันทึก" — ต้องจำแค่ว่า "ต้องปิดช่องว่าง" ซึ่งเห็นอยู่บนหน้าจอ

สิ่งที่เครื่องมือนี้ไม่ทำ: มันไม่ตัดสินว่าการเปลี่ยนแปลงปลอดภัยหรือไม่ การ
ประเมินผลกระทบและการอนุมัติเป็นวิจารณญาณของคน ระบบทำได้แค่บังคับให้มีคนเซ็น
และบันทึกว่าใครเซ็นเมื่อไร
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import (
    App, AppVersion, ChangeRecord, ChangeStatus, User,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# การเชื่อมกับชั้นตามรอย — มีก็ใช้ ไม่มีก็ทำงานได้
# --------------------------------------------------------------------------- #
#
# การควบคุมการเปลี่ยนแปลงไม่ใช่เรื่องเฉพาะเครื่องมือแพทย์ คำถามว่า "เปลี่ยนอะไร
# ทำไม กระทบอะไร ใครอนุมัติ" เป็นคำถามของทุกโครงการที่ให้ AI เขียนโค้ด และเป็น
# คำถามที่ประวัติ git ตอบไม่ได้
#
# ส่วนที่เป็นเรื่องเฉพาะทางคือการ **ผูกกับข้อกำหนด ความเสี่ยง และผลทดสอบ** ตาม
# ISO 13485 / ISO 14971 ซึ่งมีเฉพาะเมื่อติดตั้งชั้นตามรอย โมดูลนี้จึงไม่ import
# โมเดลเหล่านั้นตรง ๆ — ถ้าไม่มี ระเบียนการเปลี่ยนแปลงยังทำงานครบ เพียงไม่มี
# รหัสข้อกำหนดและผลทดสอบมาประกอบ

def _traceability_available() -> bool:
    try:
        from app.models import Requirement, RiskItem, TestRecord  # noqa: F401
        return True
    except ImportError:
        return False


def _codes_for(db: Session, kind: str, ids: List[int]) -> List[str]:
    """รหัสข้อกำหนด/ความเสี่ยงที่ผูกไว้ คืนค่าว่างถ้าไม่มีชั้นตามรอย"""
    if not ids:
        return []
    try:
        from app.models import Requirement, RiskItem
    except ImportError:
        return []
    model = Requirement if kind == "requirement" else RiskItem
    return sorted(r.code for r in db.query(model).filter(model.id.in_(ids)).all())


def _passing_test_codes(db: Session, app_id: int, version: Optional[int]) -> List[str]:
    """รหัสการทดสอบที่ผ่านของเวอร์ชันนี้ คืนค่าว่างถ้าไม่มีชั้นตามรอย"""
    if not version:
        return []
    try:
        from app.models import TestRecord
    except ImportError:
        return []
    return sorted(
        t.code for t in db.query(TestRecord).filter(
            TestRecord.app_id == app_id,
            TestRecord.app_version == version,
            TestRecord.result == "pass",
        ).all()
    )


def _parse_ids(raw: Optional[str]) -> List[int]:
    try:
        v = json.loads(raw or "[]")
        return [int(x) for x in v] if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def next_code(db: Session, app_id: int) -> str:
    """CHG-001, CHG-002, … ต่อหนึ่งแอป"""
    n = db.query(ChangeRecord).filter(ChangeRecord.app_id == app_id).count()
    while True:
        n += 1
        code = f"CHG-{n:03d}"
        exists = db.query(ChangeRecord).filter(
            ChangeRecord.app_id == app_id, ChangeRecord.code == code
        ).first()
        if not exists:
            return code


def record_deployment(
    db: Session,
    app: App,
    version: int,
    user: Optional[User] = None,
    summary: str = "",
) -> Optional[ChangeRecord]:
    """สร้างระเบียนการเปลี่ยนแปลงอัตโนมัติเมื่อปล่อยเวอร์ชันใหม่

    เรียกจากเส้นทาง redeploy หลังจากที่ AppVersion ถูกสร้าง ตัวเรียกยังไม่ต้อง
    commit — ฟังก์ชันนี้แค่ db.add() ให้เข้าไปในธุรกรรมเดียวกัน ถ้าการ deploy
    ล้มเหลวและถูก rollback ระเบียนก็หายไปด้วย ซึ่งถูกต้อง เพราะการเปลี่ยนแปลง
    ที่ไม่เคยถึงมือผู้ใช้ไม่ใช่การเปลี่ยนแปลงที่ต้องควบคุม

    ห้าม raise ออกไป — การควบคุมการเปลี่ยนแปลงเป็นงานเอกสาร ไม่ควรทำให้การ
    deploy ที่สำเร็จแล้วพัง ถ้าบันทึกไม่ได้ก็ log ไว้แล้วปล่อยผ่าน
    """
    try:
        exists = db.query(ChangeRecord).filter(
            ChangeRecord.app_id == app.id,
            ChangeRecord.app_version == version,
            ChangeRecord.origin == "auto",
        ).first()
        if exists:
            return exists

        rec = ChangeRecord(
            app_id=app.id,
            code=next_code(db, app.id),
            app_version=version,
            description=summary or f"ปล่อยเวอร์ชัน {version}",
            # เว้นว่างโดยตั้งใจ — ระบบไม่รู้ว่าทำไมถึงเปลี่ยน มีแต่คนที่รู้
            reason="",
            impact="",
            # ตั้งต้นว่ากระทบผู้ใช้ที่ติดตั้งไปแล้ว เพราะเวอร์ชันใหม่ถูกปล่อย
            # ให้ใช้งานจริงทันทีที่ deploy สำเร็จ ผู้ประเมินปลดได้ถ้าไม่จริง
            affects_released=True,
            reverify_needed=True,
            status=ChangeStatus.DRAFT,
            origin="auto",
            created_by=user.id if user else None,
        )
        db.add(rec)
        db.flush()
        return rec
    except Exception as e:
        logger.warning(f"บันทึกการเปลี่ยนแปลงอัตโนมัติไม่สำเร็จ (app={app.id} v{version}): {e}")
        return None


def to_dict(db: Session, rec: ChangeRecord) -> dict:
    req_ids = _parse_ids(rec.requirement_ids)
    risk_ids = _parse_ids(rec.risk_ids)

    req_codes = _codes_for(db, "requirement", req_ids)
    risk_codes = _codes_for(db, "risk", risk_ids)

    approver = None
    if rec.approved_by:
        u = db.query(User).filter(User.id == rec.approved_by).first()
        approver = u.username if u else None

    # การทดสอบที่ยืนยันเวอร์ชันนี้ — ตอบคำถาม "เปลี่ยนแล้วทดสอบซ้ำหรือยัง"
    verified = _passing_test_codes(db, rec.app_id, rec.app_version)

    return {
        "id": rec.id,
        "app_id": rec.app_id,
        "code": rec.code,
        "app_version": rec.app_version,
        "description": rec.description or "",
        "reason": rec.reason or "",
        "impact": rec.impact or "",
        "affects_released": bool(rec.affects_released),
        "reverify_needed": bool(rec.reverify_needed),
        "requirement_ids": req_ids,
        "risk_ids": risk_ids,
        "requirement_codes": req_codes,
        "risk_codes": risk_codes,
        "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
        "origin": rec.origin or "manual",
        "approved_by": approver,
        "approved_at": rec.approved_at.isoformat() if rec.approved_at else None,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        # ผลทดสอบที่ผูกกับเวอร์ชันนี้ ใช้ตัดสินว่าการทดสอบซ้ำเสร็จหรือยัง
        "verified_by_tests": verified,
        # ไม่มีชั้นตามรอย = ระบบไม่มีทางรู้ว่าทดสอบซ้ำหรือยัง จึงไม่อ้างว่ารู้
        "reverify_satisfied": (
            True if not rec.reverify_needed
            else (bool(verified) if _traceability_available() else None)
        ),
    }


def can_approve(rec: ChangeRecord, verified: List[str]) -> Optional[str]:
    """เหตุผลที่ยังอนุมัติไม่ได้ หรือ None ถ้าอนุมัติได้

    เงื่อนไขทั้งสองข้อมาจากข้อกำหนดตรง ๆ ไม่ใช่กฎที่เราคิดขึ้นเอง:
    ต้องประเมินผลกระทบก่อนอนุมัติ และการเปลี่ยนแปลงที่ต้องทวนสอบซ้ำจะอนุมัติ
    โดยไม่มีผลทดสอบของเวอร์ชันนั้นไม่ได้

    เงื่อนไขข้อหลังบังคับได้เฉพาะเมื่อมีชั้นตามรอยให้ตรวจ ถ้าไม่มี ระบบไม่รู้ว่า
    มีการทดสอบหรือไม่ — การห้ามอนุมัติเพราะไม่รู้ คือการอ้างข้อเท็จจริงที่ระบบ
    ไม่มี ความรับผิดชอบตกที่คนเซ็นตามเดิม
    """
    if not (rec.impact or "").strip():
        return "ต้องประเมินผลกระทบก่อนอนุมัติ"
    if rec.reverify_needed and not verified and _traceability_available():
        return f"ระบุว่าต้องทวนสอบซ้ำ แต่ยังไม่มีผลทดสอบที่ผ่านของเวอร์ชัน {rec.app_version}"
    return None


def gaps_for_app(db: Session, app_id: int) -> dict:
    """ช่องว่างด้านการควบคุมการเปลี่ยนแปลง สำหรับรวมเข้าตารางตามรอย"""
    recs = db.query(ChangeRecord).filter(ChangeRecord.app_id == app_id).all()
    # ถ้าไม่มีชั้นตามรอย ช่องว่าง "ยังไม่ทดสอบซ้ำ" ตรวจไม่ได้ จึงไม่รายงานว่าง
    # เปล่าเหมือนไม่มีปัญหา — ไม่รายงานเลย
    can_check_tests = _traceability_available()

    unassessed, unapproved, unverified = [], [], []
    for r in recs:
        if r.status == ChangeStatus.REVERTED:
            continue
        if not (r.impact or "").strip():
            unassessed.append(r.code)
        if r.status != ChangeStatus.APPROVED:
            unapproved.append(r.code)
        if can_check_tests and r.reverify_needed and r.app_version:
            if not _passing_test_codes(db, app_id, r.app_version):
                unverified.append(r.code)

    return {
        # เปลี่ยนแล้วแต่ไม่มีใครประเมินว่ากระทบอะไร
        "changes_unassessed": sorted(unassessed),
        # ประเมินแล้วแต่ยังไม่มีใครอนุมัติ
        "changes_unapproved": sorted(unapproved),
        # ต้องทดสอบซ้ำแต่ยังไม่มีผลทดสอบของเวอร์ชันนั้น
        "changes_unverified": sorted(unverified),
    }


def versions_without_change(db: Session, app_id: int) -> List[int]:
    """เวอร์ชันที่ปล่อยไปแล้วแต่ไม่มีระเบียนการเปลี่ยนแปลง

    ควรว่างเปล่าสำหรับทุกอย่างที่ deploy หลังติดตั้งรุ่นนี้ ถ้าไม่ว่างแปลว่า
    เป็นเวอร์ชันเก่าที่มีอยู่ก่อน — บอกตรง ๆ ดีกว่าเงียบ ผู้ตรวจจะถามอยู่ดี
    """
    versions = {v.version for v in db.query(AppVersion).filter(
        AppVersion.app_id == app_id).all()}
    covered = {r.app_version for r in db.query(ChangeRecord).filter(
        ChangeRecord.app_id == app_id).all() if r.app_version}
    return sorted(versions - covered)


def approve(db: Session, rec: ChangeRecord, user: User) -> None:
    rec.status = ChangeStatus.APPROVED
    rec.approved_by = user.id
    rec.approved_at = datetime.utcnow()
