"""ROPA — who receives the data, and whether a deletion request must be honoured.

iVS already keeps a Record of Processing Activities with one app as one
activity. That holds as long as an app's data stays inside the app. Once apps
exchange data, an API is opened, or an AI model is allowed to read it, the
activity has gained a recipient — and a recipient that appears nowhere in the
ROPA or in the privacy notice is a recipient the data subject was never told
about.

So recipients are recorded here, and recorded automatically wherever iVS itself
opens a path, rather than relying on someone remembering to write it down.

The erasure question is the other half. "Delete my data" is not a switch: under
PDPA §33 the right to erasure depends on the lawful basis the activity relies on
(§24). Data kept to satisfy a legal obligation cannot be deleted on request —
deleting it would itself be the violation. So a request names an activity, and
this module answers whether that activity gives the right, from the basis
recorded for it rather than from anyone's discretion.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import AppPdpa

logger = logging.getLogger(__name__)

# ── ฐานการประมวลผล (ม.24) → สิทธิขอให้ลบ (ม.33) ────────────────────
#
# `True`  = การลบเป็นสิทธิของเจ้าของข้อมูลโดยหลัก
# `False` = ฐานนี้ทำให้การลบตามคำขอทำไม่ได้ ต้องอธิบายเหตุผลกลับไป
LEGAL_BASIS = {
    "consent": {
        "th": "ความยินยอม (ม.24)",
        "en": "Consent",
        "erasable": True,
        "why": "ถอนความยินยอมได้ เมื่อถอนแล้วไม่มีฐานให้เก็บต่อ",
    },
    "contract": {
        "th": "การปฏิบัติตามสัญญา (ม.24(3))",
        "en": "Performance of a contract",
        "erasable": False,
        "why": "ยังต้องใช้เพื่อปฏิบัติตามสัญญาที่ยังมีผลอยู่ ลบได้เมื่อสัญญาสิ้นสุดและพ้นระยะเก็บ",
    },
    "legal_obligation": {
        "th": "การปฏิบัติตามกฎหมาย (ม.24(6))",
        "en": "Legal obligation",
        "erasable": False,
        "why": "กฎหมายกำหนดให้เก็บ การลบตามคำขอจะเป็นการทำผิดกฎหมายเสียเอง",
    },
    "vital_interest": {
        "th": "การป้องกันอันตรายต่อชีวิต ร่างกาย สุขภาพ (ม.24(1))",
        "en": "Vital interest",
        "erasable": False,
        "why": "เก็บเพื่อป้องกันอันตรายต่อชีวิตหรือสุขภาพ",
    },
    "public_task": {
        "th": "ภารกิจของรัฐ (ม.24(4))",
        "en": "Public task",
        "erasable": False,
        "why": "จำเป็นต่อการปฏิบัติหน้าที่ของหน่วยงานรัฐ",
    },
    "legitimate_interest": {
        "th": "ประโยชน์โดยชอบด้วยกฎหมาย (ม.24(5))",
        "en": "Legitimate interest",
        "erasable": True,
        "why": "เจ้าของข้อมูลคัดค้านได้ตาม ม.32 และขอให้ลบได้หากไม่มีเหตุอันชอบที่เหนือกว่า",
    },
}

RECIPIENT_KINDS = {"app", "external", "ai"}


# ── ผู้รับข้อมูล ─────────────────────────────────────────────────────

def get_recipients(record: AppPdpa) -> List[dict]:
    try:
        data = json.loads(record.data_recipients or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def add_recipient(
    db: Session, record: AppPdpa, kind: str, name: str,
    purpose: str = "", note: str = "",
) -> Tuple[bool, List[dict]]:
    """Record that this activity now discloses data to `name`.

    Returns (added, recipients). Adding the same recipient twice is a no-op, so
    callers can call this on every open without checking first.

    Meant to be called by iVS itself when it opens a path — an API, an MCP tool,
    an export — so the ROPA reflects what the system actually does rather than
    what someone remembered to record.
    """
    if kind not in RECIPIENT_KINDS:
        kind = "external"
    name = (name or "").strip()
    if not name:
        return False, get_recipients(record)

    recipients = get_recipients(record)
    for r in recipients:
        if r.get("kind") == kind and r.get("name") == name:
            return False, recipients

    recipients.append({
        "kind": kind,
        "name": name[:200],
        "purpose": (purpose or "")[:500],
        "note": (note or "")[:500],
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    record.data_recipients = json.dumps(recipients, ensure_ascii=False)
    db.commit()
    logger.info(f"ROPA: app_id={record.app_id} gained recipient {kind}:{name}")
    return True, recipients


def remove_recipient(db: Session, record: AppPdpa, kind: str, name: str) -> List[dict]:
    recipients = [
        r for r in get_recipients(record)
        if not (r.get("kind") == kind and r.get("name") == name)
    ]
    record.data_recipients = json.dumps(recipients, ensure_ascii=False)
    db.commit()
    return recipients


# ── สิทธิขอให้ลบ ────────────────────────────────────────────────────

def erasure_decision(record: Optional[AppPdpa]) -> dict:
    """Whether a deletion request against this activity has to be honoured.

    An explicit setting wins over the basis, because there are real cases the
    table can't know — consent-based data that is also under a retention order,
    for instance. But an override has to carry a reason, since that reason is
    what gets sent back to the person who asked.
    """
    if record is None:
        return {
            "erasable": False,
            "reason_th": "ยังไม่ได้บันทึกกิจกรรมนี้ใน ROPA จึงยังตอบคำขอลบไม่ได้",
            "basis": "",
            "basis_label": "",
            "source": "missing",
        }

    basis = (record.legal_basis or "").strip()
    info = LEGAL_BASIS.get(basis)
    setting = (record.erasure_right or "auto").strip()

    if setting == "allowed":
        return {
            "erasable": True,
            "reason_th": record.erasure_note or "ผู้ควบคุมข้อมูลกำหนดให้ลบได้ตามคำขอ",
            "basis": basis,
            "basis_label": info["th"] if info else "",
            "source": "override",
        }
    if setting == "restricted":
        return {
            "erasable": False,
            "reason_th": record.erasure_note or "ผู้ควบคุมข้อมูลกำหนดว่ากิจกรรมนี้ลบตามคำขอไม่ได้",
            "basis": basis,
            "basis_label": info["th"] if info else "",
            "source": "override",
        }

    if not info:
        return {
            "erasable": False,
            "reason_th": "ยังไม่ได้ระบุฐานการประมวลผลของกิจกรรมนี้ จึงยังตัดสินคำขอลบไม่ได้",
            "basis": "",
            "basis_label": "",
            "source": "unset",
        }

    return {
        "erasable": info["erasable"],
        "reason_th": info["why"],
        "basis": basis,
        "basis_label": info["th"],
        "source": "legal_basis",
    }


def basis_options() -> List[dict]:
    """The lawful bases, for the UI to offer."""
    return [
        {"value": k, "label_th": v["th"], "label_en": v["en"],
         "erasable": v["erasable"], "why": v["why"]}
        for k, v in LEGAL_BASIS.items()
    ]
