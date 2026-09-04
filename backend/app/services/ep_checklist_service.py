"""Essential Principles checklist สำหรับการยื่นขึ้นทะเบียนเครื่องมือแพทย์

เอกสารนี้บังคับทั้งช่องทาง Full และ Abridged และเป็นเอกสารที่ผู้ประเมินอ่านก่อน
เพื่อดูภาพรวมว่าผลิตภัณฑ์อ้างความสอดคล้องกับอะไรบ้าง และหลักฐานอยู่ที่ไหน

**สามช่องต่อหนึ่งแถว**

แต่ละหลักการต้องตอบว่า ใช้กับผลิตภัณฑ์นี้หรือไม่ · แสดงความสอดคล้องด้วยวิธีใด ·
และหลักฐานอยู่ในเอกสารฉบับไหน ช่องที่สามคือช่องที่แยกเอกสารฉบับจริงออกจาก
แบบฟอร์มติ๊กถูก — การเขียนว่า "สอดคล้องตาม ISO 14971" โดยไม่ระบุเลขที่แฟ้ม
จัดการความเสี่ยง คือคำกล่าวอ้างที่ตรวจสอบไม่ได้

**เรื่องข้อความของหลักการ**

โมดูลนี้เก็บเฉพาะ *หัวข้อ* ของหลักการ ไม่ได้เก็บถ้อยคำเต็มของแต่ละข้อ เพราะ
ถ้อยคำต้องคัดจากแม่แบบที่เลือกใช้จริง — ASEAN Medical Device Directive ภาคผนวก 1
หรือ Essential Principles ของ HSA สิงคโปร์ หรือ General Safety and Performance
Requirements ของสหภาพยุโรป การเขียนถ้อยคำขึ้นเองแล้วยื่นไป คือการยื่นเอกสารที่
ไม่ตรงกับแม่แบบใดเลย

**ทำไมต้องรู้ว่าเป็น SaMD**

หลักการส่วนใหญ่เขียนไว้สำหรับเครื่องมือที่มีตัวตนทางกายภาพ — ความปลอดภัยทางไฟฟ้า
การปลอดเชื้อ วัสดุชีวภาพ รังสี ซอฟต์แวร์ล้วนไม่เข้าข่ายเหล่านั้น เอกสารของ HSA
จึงมีตารางระบุว่าข้อใดใช้กับ SaMD บ้าง โมดูลนี้ตั้งค่าเริ่มต้นตามตารางนั้นให้
เพื่อไม่ให้ต้องไล่ตอบทีละข้อว่า "ไม่เกี่ยว" แต่ผู้ใช้ปรับได้ทุกข้อ เพราะการ
ตัดสินสุดท้ายเป็นของผู้รับผิดชอบ ไม่ใช่ของค่าตั้งต้น
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import EpChecklist, User

logger = logging.getLogger(__name__)

TEMPLATES: Dict[str, str] = {
    "amdd": "ASEAN Medical Device Directive (AMDD) ภาคผนวก 1",
    "hsa":  "Essential Principles ของ HSA สิงคโปร์ (GN-16)",
    "eu":   "EU General Safety and Performance Requirements",
}

# หัวข้อหลักการ พร้อมค่าเริ่มต้นว่าใช้กับ SaMD หรือไม่
# ค่า applies_to_samd ถอดจากตารางในเอกสารแนวทางการขึ้นทะเบียน SaMD ซึ่งอ้าง
# Regulatory Guidelines for Software Medical Devices – A Life Cycle Approach ของ HSA
PRINCIPLES: List[dict] = [
    {"code": "EP-GEN", "title": "ข้อกำหนดทั่วไป — ออกแบบและผลิตให้ปลอดภัยเมื่อใช้ตามวัตถุประสงค์",
     "samd": True,
     "hint": "โดยทั่วไปแสดงความสอดคล้องด้วย ISO 14971 และ ISO 13485 ร่วมกัน"},
    {"code": "EP-CLIN", "title": "การประเมินทางคลินิก (Clinical evaluation)", "samd": True,
     "hint": "ทบทวนวรรณกรรม ประสบการณ์การใช้ หรือการศึกษาทางคลินิก"},
    {"code": "EP-CHEM", "title": "สมบัติทางเคมี กายภาพ และชีวภาพ", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์ที่ไม่มีตัวตนทางกายภาพ"},
    {"code": "EP-STERILE", "title": "การปลอดเชื้อ บรรจุภัณฑ์ และการปนเปื้อนจุลชีพ", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-ENV", "title": "การพิจารณาสภาพแวดล้อมและเงื่อนไขการใช้งาน", "samd": True,
     "hint": "ระบุสภาพแวดล้อมที่ใช้ ความเข้ากันได้ของฮาร์ดแวร์และระบบปฏิบัติการ"},
    {"code": "EP-ACTIVE", "title": "เครื่องมือแพทย์ที่ต่อกับหรือมีแหล่งพลังงาน", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์ที่ทำงานอิสระ"},
    {"code": "EP-SW", "title": "เครื่องมือแพทย์ที่มีซอฟต์แวร์ หรือเป็นซอฟต์แวร์ในตัวเอง", "samd": True,
     "hint": "ข้อหลักของ SaMD — แสดงความสอดคล้องด้วย IEC 62304 พร้อมรายงานผลการทดสอบ"},
    {"code": "EP-DIAG", "title": "เครื่องมือแพทย์ที่มีหน้าที่วินิจฉัยหรือวัดค่า", "samd": True,
     "hint": "ความแม่นยำ ความเที่ยง และขีดจำกัดของการวัดหรือการวินิจฉัย"},
    {"code": "EP-LABEL", "title": "ฉลากและเอกสารกำกับการใช้งาน", "samd": True,
     "hint": "ประกาศกระทรวงสาธารณสุข พ.ศ. 2568 · ISO 20417 · ISO 15223"},
    {"code": "EP-ELEC", "title": "การป้องกันความเสี่ยงทางไฟฟ้า เชิงกล และความร้อน", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-RAD", "title": "การป้องกันความเสี่ยงจากรังสี", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-LAY", "title": "การป้องกันความเสี่ยงเมื่อเจ้าของผลิตภัณฑ์มุ่งหมายให้ผู้ใช้ทั่วไปใช้",
     "samd": True,
     "hint": "ใช้เมื่อผู้ใช้เป็นผู้ป่วยหรือผู้ดูแล — IEC 62366-1 วิศวกรรมการใช้งาน"},
    {"code": "EP-BIO", "title": "เครื่องมือแพทย์ที่มีวัสดุจากแหล่งกำเนิดทางชีวภาพ", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-IMPLANT", "title": "ข้อกำหนดเฉพาะสำหรับเครื่องมือแพทย์ฝังในร่างกาย", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-ENERGY", "title": "การป้องกันความเสี่ยงจากเครื่องมือที่ส่งพลังงานหรือสารเข้าร่างกาย",
     "samd": False, "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-DRUG", "title": "เครื่องมือแพทย์ที่มีสารซึ่งถือเป็นยาเป็นส่วนประกอบ", "samd": False,
     "hint": "ปกติไม่ใช้กับซอฟต์แวร์"},
    {"code": "EP-PERF", "title": "คุณลักษณะด้านสมรรถนะ (Performance characteristics)", "samd": True,
     "hint": "สมรรถนะเป็นไปตามที่ประกาศไว้ ภายใต้เงื่อนไขการใช้งานที่ระบุ"},
]

PRINCIPLE_INDEX = {p["code"]: p for p in PRINCIPLES}


def _load(raw: Optional[str]) -> List[dict]:
    try:
        v = json.loads(raw or "[]")
        return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def default_rows() -> List[dict]:
    """ตั้งค่าเริ่มต้นตามตารางความเกี่ยวข้องกับ SaMD ของ HSA

    ตั้งให้เฉพาะช่อง "ใช้หรือไม่" ส่วนวิธีแสดงความสอดคล้องและเลขเอกสารเว้นว่างไว้
    เพราะสองช่องนั้นไม่มีค่าเริ่มต้นที่ถูกต้อง — ต้องมาจากเอกสารจริงขององค์กร
    """
    return [
        {"code": p["code"], "applicable": p["samd"], "method": "", "docs": "", "note": ""}
        for p in PRINCIPLES
    ]


def to_dict(db: Session, row: EpChecklist) -> dict:
    rows = _load(row.rows) or default_rows()
    by_code = {r.get("code"): r for r in rows}
    merged = []
    for p in PRINCIPLES:
        r = by_code.get(p["code"], {})
        merged.append({
            "code": p["code"],
            "title": p["title"],
            "hint": p["hint"],
            "samd_default": p["samd"],
            "applicable": bool(r.get("applicable", p["samd"])),
            "method": r.get("method", ""),
            "docs": r.get("docs", ""),
            "note": r.get("note", ""),
        })
    who = None
    if row.updated_by:
        u = db.query(User).filter(User.id == row.updated_by).first()
        who = u.username if u else None
    return {
        "app_id": row.app_id,
        "template": row.template or "amdd",
        "template_label": TEMPLATES.get(row.template or "amdd", ""),
        "rows": merged,
        "prepared_by": row.prepared_by or "", "prepared_role": row.prepared_role or "",
        "reviewed_by": row.reviewed_by or "", "reviewed_role": row.reviewed_role or "",
        "approved_by": row.approved_by or "", "approved_role": row.approved_role or "",
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "updated_by": who,
        "summary": summarize(merged),
    }


def summarize(rows: List[dict]) -> dict:
    applicable = [r for r in rows if r.get("applicable")]
    complete = [r for r in applicable
                if (r.get("method") or "").strip() and (r.get("docs") or "").strip()]
    return {
        "total": len(rows),
        "applicable": len(applicable),
        "complete": len(complete),
        "percent": round(100 * len(complete) / len(applicable)) if applicable else 0,
    }


def apply(row: EpChecklist, payload: dict, user: User) -> None:
    if payload.get("template") in TEMPLATES:
        row.template = payload["template"]
    if "rows" in payload:
        clean = []
        for r in payload["rows"]:
            code = r.get("code")
            if code not in PRINCIPLE_INDEX:
                continue
            clean.append({
                "code": code,
                "applicable": bool(r.get("applicable")),
                "method": (r.get("method") or "")[:300],
                "docs": (r.get("docs") or "")[:300],
                "note": (r.get("note") or "")[:1000],
            })
        row.rows = json.dumps(clean, ensure_ascii=False)
    for f in ("prepared_by", "prepared_role", "reviewed_by",
              "reviewed_role", "approved_by", "approved_role"):
        if f in payload:
            setattr(row, f, (payload.get(f) or "")[:120])
    # ประทับเวลาอนุมัติเมื่อมีชื่อผู้อนุมัติครบเป็นครั้งแรก
    if (row.approved_by or "").strip() and not row.approved_at:
        row.approved_at = datetime.utcnow()
    if not (row.approved_by or "").strip():
        row.approved_at = None
    row.updated_by = user.id


def gaps_for_app(db: Session, app_id: int) -> dict:
    """ช่องว่างของ checklist — เอกสารระบุว่าต้องครบถ้วนและมีการลงนาม"""
    row = db.query(EpChecklist).filter(EpChecklist.app_id == app_id).first()
    if not row:
        return {}

    data = to_dict(db, row)
    no_method, no_docs = [], []
    for r in data["rows"]:
        if not r["applicable"]:
            continue
        if not (r["method"] or "").strip():
            no_method.append(r["code"])
        elif not (r["docs"] or "").strip():
            # ระบุวิธีแล้วแต่ไม่บอกว่าหลักฐานอยู่ไฟล์ไหน คือข้ออ้างที่ตรวจไม่ได้
            no_docs.append(r["code"])

    out: Dict[str, List[str]] = {}
    if no_method:
        out["ep_no_method"] = sorted(no_method)
    if no_docs:
        out["ep_no_evidence"] = sorted(no_docs)

    missing_sign = []
    if not (row.prepared_by or "").strip():
        missing_sign.append("ผู้จัดทำ")
    if not (row.reviewed_by or "").strip():
        missing_sign.append("ผู้ทบทวน")
    if not (row.approved_by or "").strip():
        missing_sign.append("ผู้อนุมัติ")
    if missing_sign:
        out["ep_unsigned"] = missing_sign
    return out
