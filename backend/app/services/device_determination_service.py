"""วินิจฉัยว่าโปรแกรมบน iVS เข้าข่ายเครื่องมือแพทย์หรือไม่

ตามนิยามมาตรา 4 แห่ง พ.ร.บ. เครื่องมือแพทย์ พ.ศ. 2551 และแก้ไขเพิ่มเติม

**ทำไมขั้นตอนนี้ต้องมาก่อนการควบคุมการออกแบบ**

ลำดับที่ อย. วางไว้คือ วินิจฉัยก่อน แล้วจึงพัฒนาตามระบบคุณภาพ แล้วจึงขึ้นทะเบียน
การข้ามขั้นแรกทำให้พลาดได้สองทางและทั้งสองทางแพง — เข้าข่ายแล้วไม่ขึ้นทะเบียน คือ
ผิดกฎหมายตั้งแต่วันแรกที่นำออกใช้ ส่วนไม่เข้าข่ายแล้วไปทำระบบคุณภาพเต็มรูปแบบ คือ
จ่ายค่าใช้จ่ายที่ไม่มีใครเรียกร้อง

**ตัวชี้ขาดคือวัตถุประสงค์ ไม่ใช่ความสามารถ**

นิยามเขียนว่า "ผู้ผลิตหรือเจ้าของผลิตภัณฑ์ **มุ่งหมายเฉพาะ**" โปรแกรมสองตัวที่
ทำงานเหมือนกันทุกอย่างจึงอาจถูกจัดคนละประเภทได้ ขึ้นกับว่าเจ้าของประกาศว่าใช้ทำอะไร
ตัวอย่างที่ อย. ยกไว้เอง: แอปนับแคลอรีด้วย AI ไม่ใช่เครื่องมือแพทย์ ส่วนแอปประเมิน
ความเสี่ยงโรคหลอดเลือดสมองโป่งพองเป็นเครื่องมือแพทย์ ทั้งที่ทั้งคู่คือซอฟต์แวร์
ที่รับข้อมูลผู้ใช้แล้วคำนวณผลออกมา

**และการเขียนว่า "ไม่ใช้ทางการแพทย์" ไม่ได้ช่วยเสมอไป**

จุดนี้สำคัญและคนพลาดกันมาก อย. ระบุไว้ว่าถ้าฟังก์ชันนั้นยังไม่มีเอกสารทางวิชาการ
หรือข้อมูลการใช้งานระดับสากลที่รองรับว่ามีการใช้ทางอื่นนอกเหนือจากทางการแพทย์
ต่อให้เจ้าของประกาศว่า "For information only" ก็ยังถือเป็นเครื่องมือแพทย์
เช่น ความดันโลหิต อัตราการหายใจ น้ำตาลในเลือด ภาวะหยุดหายใจขณะหลับ และอุณหภูมิ
แกนกลางร่างกาย โมดูล `ALWAYS_REGULATED` ด้านล่างจึงมีไว้เตือนเรื่องนี้โดยเฉพาะ

**สิ่งที่เครื่องมือนี้ไม่ใช่**

เป็นการประเมินตนเองเพื่อเตรียมตัว ไม่ใช่คำวินิจฉัยที่มีผลทางกฎหมาย ผู้มีอำนาจ
วินิจฉัยคือกองควบคุมเครื่องมือแพทย์ สำนักงานคณะกรรมการอาหารและยา เท่านั้น
กรณีก้ำกึ่งควรยื่นขอคำวินิจฉัยอย่างเป็นทางการ
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    App, DeviceDetermination, DeviceVerdict, User,
)

logger = logging.getLogger(__name__)

# ── นิยามมาตรา 4 (1) ข้อ (ก) ถึง (ซ) ──────────────────────────
# ถ้อยคำคัดตามตัวบท เพื่อให้ผู้ประเมินอ่านแล้วเทียบกับผลิตภัณฑ์ของตัวเองได้ตรง
PURPOSES: Dict[str, str] = {
    "ก": "วินิจฉัย ป้องกัน ติดตาม บำบัด บรรเทา หรือรักษาโรค",
    "ข": "วินิจฉัย ติดตาม บำบัด บรรเทา หรือรักษาการบาดเจ็บ",
    "ค": "ตรวจสอบ ทดแทน แก้ไข ดัดแปลง พยุง ค้ำ หรือจุนด้านกายวิภาคหรือกระบวนการทางสรีระของร่างกาย",
    "ง": "ประคับประคองหรือช่วยชีวิต",
    "จ": "คุมกำเนิด หรือช่วยการเจริญพันธุ์",
    "ฉ": "ช่วยเหลือหรือชดเชยความทุพพลภาพหรือพิการ",
    "ช": "ให้ข้อมูลจากการตรวจสิ่งส่งตรวจจากร่างกาย เพื่อวัตถุประสงค์ทางการแพทย์หรือการวินิจฉัย",
    "ซ": "ทำลายหรือฆ่าเชื้อสำหรับเครื่องมือแพทย์",
}

# ฟังก์ชันที่ อย. ถือเป็นเครื่องมือแพทย์แม้เจ้าของจะประกาศว่าไม่ใช้ทางการแพทย์
# เพราะยังไม่มีหลักฐานระดับสากลว่ามีการใช้ทางอื่นนอกเหนือจากทางการแพทย์
ALWAYS_REGULATED: Dict[str, str] = {
    "bp":      "ความดันโลหิต (Blood pressure)",
    "rr":      "อัตราการหายใจ (Respiratory rate)",
    "glucose": "ระดับน้ำตาลในเลือด (Blood glucose)",
    "apnea":   "ภาวะหยุดหายใจขณะหลับ (Sleep apnea)",
    "coretemp": "อุณหภูมิแกนกลางร่างกาย (Core body temperature)",
}

# ตัวอย่างที่ อย. ใช้สอน เก็บไว้ให้ผู้ประเมินเทียบเคียง
REFERENCE_CASES = [
    # เข้าข่าย — จากเอกสารแนวทางการขึ้นทะเบียน SaMD ของกองควบคุมเครื่องมือแพทย์
    ("ซอฟต์แวร์วิเคราะห์คลื่นไฟฟ้าหัวใจช่วยวินิจฉัยภาวะหัวใจเต้นผิดจังหวะ", True,
     "วิเคราะห์ข้อมูลเพื่อช่วยวินิจฉัย เข้าข้อ (ก)"),
    ("ซอฟต์แวร์วิเคราะห์ภาพรอยโรคผิวหนัง แยก malignant กับ benign", True,
     "คัดกรองโรค เข้าข้อ (ก) — เอกสาร อย. จัดเป็นประเภทที่ 2 หลักเกณฑ์ 10(1)"),
    ("แอปวิเคราะห์รูปถ่ายไฝเพื่อประเมินความเสี่ยงมะเร็งผิวหนัง", True,
     "ประเมินความเสี่ยงของโรค เข้าข้อ (ก)"),
    ("แอปคุมกำเนิดไม่ใช้ฮอร์โมน", True,
     "มุ่งหมายเพื่อคุมกำเนิด เข้าข้อ (จ) โดยตรง"),
    # ไม่เข้าข่าย — กลุ่มนี้สำคัญที่สุดสำหรับระบบงานทั่วไปในโรงพยาบาล
    ("ระบบเวชระเบียนอิเล็กทรอนิกส์ (EHR) ที่แสดง รับ รวบรวม จัดเก็บ", False,
     "ไม่มีการประมวลผลหรือวิเคราะห์ จึงไม่เข้าวัตถุประสงค์ทางการแพทย์"),
    ("ระบบจัดการนัดหมายผู้ป่วยและตารางการผ่าตัด", False,
     "เป็นงานบริหารจัดการ ไม่ได้มุ่งวินิจฉัยหรือรักษา"),
    ("ระบบเรียกเก็บเงินผู้ป่วย", False, "เป็นงานการเงิน ไม่ใช่วัตถุประสงค์ทางการแพทย์"),
    ("ระบบสารสนเทศห้องปฏิบัติการ (LIS/LIMS)", False,
     "สนับสนุนขั้นตอนการทำงานและติดตามข้อมูล ไม่ได้แปลผลทางคลินิก"),
    ("เครื่องคิดเลขทางการแพทย์อย่างง่าย เช่น BMI หรือแปลงหน่วย", False,
     "คำนวณค่าตรงไปตรงมา ไม่ได้ให้ข้อสรุปทางคลินิก"),
    ("ซอฟต์แวร์สื่อสารทางไกลระหว่างแพทย์กับผู้ป่วย (telemedicine)", False,
     "เป็นช่องทางสื่อสาร ไม่ได้ประมวลผลเพื่อวัตถุประสงค์ทางการแพทย์"),
    ("ซอฟต์แวร์รับและจัดเก็บภาพจากกล้องส่องตรวจ", False,
     "รับ บันทึก และจัดการไฟล์ ไม่ได้ตีความผลทางคลินิก"),
]

# ── ประเภทของซอฟต์แวร์ในระบบสุขภาพ ────────────────────────────
# เอกสาร อย. แยกไว้สี่กลุ่ม สองกลุ่มแรกอยู่นอกการกำกับ สองกลุ่มหลังอยู่ในการกำกับ
SOFTWARE_KINDS: Dict[str, str] = {
    "wellness":  "ซอฟต์แวร์เพื่อสุขภาวะทั่วไป (Software as wellness) — นอกการกำกับ",
    "nonmedical": "ซอฟต์แวร์ที่ไม่มีวัตถุประสงค์ทางการแพทย์ — นอกการกำกับ",
    "samd":      "SaMD — ทำงานอย่างอิสระ ไม่เป็นองค์ประกอบของเครื่องมือแพทย์ใด",
    "simd":      "SiMD — ฝังอยู่ในหรือควบคุมการทำงานของเครื่องมือแพทย์",
}

# ── บทบาทของซอฟต์แวร์ต่อการตัดสินใจทางคลินิก ──────────────────
# แกนแรกของการจัดระดับ เรียงจากผลกระทบน้อยไปมาก
SAMD_ROLE: Dict[str, str] = {
    "inform":  "ให้ข้อมูลทางคลินิก โดยผู้ใช้เป็นผู้ตัดสินใจเองทั้งหมด",
    "drive":   "วินิจฉัย คัดกรอง หรือวางแผนการรักษา",
    "monitor": "ติดตามกระบวนการทางสรีรวิทยาที่สำคัญต่อชีวิตโดยตรง",
    "control": "ควบคุมหรือติดตามเครื่องมือแพทย์ จนมีผลโดยตรงต่อสมรรถนะของเครื่องนั้น",
}

# ── ความวิกฤตของสภาวะที่เกี่ยวข้อง ────────────────────────────
# แกนที่สอง — นิยามตามเอกสาร อย.
SAMD_CONDITION: Dict[str, str] = {
    "non_critical": "ไม่วิกฤต — การรักษาไม่ต้องใช้วิธีซับซ้อน และไม่เร่งด่วนถึงระดับที่ต้องทำทันที",
    "critical": "วิกฤต — อาจทำให้สุขภาพเสื่อมอย่างรุนแรง พิการถาวร หรือเสียชีวิต",
}



def _load(raw: Optional[str]) -> List[str]:
    try:
        v = json.loads(raw or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def next_code(db: Session, app_id: int) -> str:
    n = db.query(DeviceDetermination).filter(
        DeviceDetermination.app_id == app_id).count()
    while True:
        n += 1
        code = f"MDD-{n:03d}"
        if not db.query(DeviceDetermination).filter(
                DeviceDetermination.app_id == app_id,
                DeviceDetermination.code == code).first():
            return code


def decide(
    target: str,
    purposes: List[str],
    pharmacological: bool,
    is_accessory: bool,
    disclaims_medical: bool,
    measures_regulated: List[str],
) -> Tuple[DeviceVerdict, List[str]]:
    """เดินตามนิยามมาตรา 4 ตามลำดับ คืนผลและเหตุผลทีละข้อ

    ลำดับการตัดสินสำคัญ — ข้อที่ตัดออกได้เด็ดขาดต้องมาก่อน เพื่อไม่ให้ผลิตภัณฑ์
    ที่ไม่เกี่ยวกับมนุษย์เลยถูกลากเข้าไปตอบคำถามที่ไม่จำเป็น
    """
    why: List[str] = []

    # ── ด่านแรก: มุ่งหมายใช้กับมนุษย์หรือสัตว์หรือไม่ ──
    if target not in ("human", "animal", "both"):
        why.append(
            "ไม่ได้มุ่งหมายให้ใช้กับมนุษย์หรือสัตว์ จึงไม่เข้าองค์ประกอบแรกของนิยามมาตรา 4"
        )
        return DeviceVerdict.NOT_DEVICE, why

    # ── ด่านที่สอง: ฟังก์ชันที่ควบคุมเสมอ ตัดสินก่อนคำประกาศของเจ้าของ ──
    if measures_regulated:
        names = ", ".join(ALWAYS_REGULATED.get(k, k) for k in measures_regulated)
        why.append(f"วัดค่าที่ อย. ถือเป็นเครื่องมือแพทย์เสมอ: {names}")
        if disclaims_medical:
            why.append(
                "แม้ประกาศว่าไม่ใช้ทางการแพทย์ ก็ไม่ทำให้พ้นนิยาม เพราะยังไม่มีเอกสาร"
                "ทางวิชาการหรือข้อมูลการใช้งานระดับสากลรองรับว่ามีการใช้ทางอื่น"
            )
        return DeviceVerdict.IS_DEVICE, why

    # ── ด่านที่สาม: อุปกรณ์เสริมตามนิยาม (2) ──
    if is_accessory:
        why.append(
            "มุ่งหมายเฉพาะให้ใช้ร่วมกับเครื่องมือแพทย์ เพื่อช่วยให้เครื่องมือแพทย์นั้น"
            "ใช้งานได้ตามวัตถุประสงค์ เข้านิยามมาตรา 4 (2)"
        )
        return DeviceVerdict.ACCESSORY, why

    # ── ด่านที่สี่: เข้าข้อ (ก)–(ซ) หรือไม่ ──
    valid = [p for p in purposes if p in PURPOSES]
    if not valid:
        why.append(
            "ไม่เข้าวัตถุประสงค์ข้อใดใน (ก) ถึง (ซ) ของนิยามมาตรา 4 (1)"
        )
        if disclaims_medical:
            why.append("และเจ้าของผลิตภัณฑ์ประกาศไว้ชัดว่าไม่ได้มุ่งหมายใช้ทางการแพทย์")
        return DeviceVerdict.NOT_DEVICE, why

    for p in valid:
        why.append(f"เข้าข้อ ({p}) {PURPOSES[p]}")

    # ── ด่านที่ห้า: ข้อยกเว้นท้ายนิยาม ──
    # ผลสัมฤทธิ์ต้องไม่เกิดจากเภสัชวิทยา ภูมิคุ้มกัน หรือเผาผลาญเป็นหลัก
    if pharmacological:
        why.append(
            "แต่ผลสัมฤทธิ์เกิดจากกระบวนการทางเภสัชวิทยา วิทยาภูมิคุ้มกัน หรือปฏิกิริยา"
            "เผาผลาญให้เกิดพลังงานเป็นหลัก จึงตกนิยามเครื่องมือแพทย์ และอาจเข้าข่ายยาแทน"
        )
        why.append("กรณีเช่นนี้ควรยื่นขอคำวินิจฉัยจาก อย. ก่อนดำเนินการต่อ")
        return DeviceVerdict.NEEDS_RULING, why

    return DeviceVerdict.IS_DEVICE, why


def classify_samd(
    software_kind: str,
    role: str,
    condition: str,
    purposes: List[str],
) -> Tuple[Optional[int], str, str]:
    """จัดระดับความเสี่ยงตามหลักเกณฑ์ที่ 9–12 (เครื่องมือแพทย์ที่มีกำลัง)

    เกณฑ์ของ อย. ใช้สองแกนร่วมกัน — **บทบาทของซอฟต์แวร์ต่อการตัดสินใจ** และ
    **ความวิกฤตของสภาวะ** ตารางด้านล่างจึงไม่ใช่การเดา แต่ถอดมาจากตารางในเอกสาร
    แนวทางการขึ้นทะเบียน SaMD โดยตรง

    | บทบาท \\ สภาวะ | ไม่วิกฤต | วิกฤต |
    |---|---|---|
    | ให้ข้อมูลทางคลินิก | ประเภท 1 ข้อ 12 | ประเภท 2 ข้อ 10(1) |
    | วินิจฉัย/คัดกรอง/วางแผนรักษา | ประเภท 2 ข้อ 10(1) | ประเภท 3 ข้อ 10(1) |
    | ติดตามสรีรวิทยาสำคัญต่อชีวิต | ประเภท 2 ข้อ 10(1) | ประเภท 3 ข้อ 10(1) |
    | ควบคุม/ติดตามเครื่องมือแพทย์ | ประเภท 3 ข้อ 9(2) | ประเภท 3 ข้อ 9(2) |

    คืนค่า (ระดับ, หลักเกณฑ์, หมายเหตุ) — ทั้งสามค่าเป็นข้อเสนอ ผู้รับผิดชอบ
    ต้องยืนยันโดยอ่านคู่มือหลักเกณฑ์การจัดประเภทประกอบ
    """
    # SiMD ไม่ประเมินแยก — ระดับขึ้นกับเครื่องมือแพทย์ทั้งเครื่องที่มันฝังอยู่
    if software_kind == "simd":
        return None, "", (
            "SiMD ไม่จัดระดับแยกจากตัวเครื่อง — ระดับความเสี่ยงขึ้นกับวัตถุประสงค์"
            "ทางการแพทย์ของเครื่องมือแพทย์ทั้งเครื่อง (hardware + SiMD) "
            "ต้องพิจารณาร่วมกับผู้ผลิตเครื่องนั้น"
        )

    if not role:
        return None, "", "ยังไม่ได้ระบุบทบาทของซอฟต์แวร์ จึงจัดระดับไม่ได้"

    critical = condition == "critical"
    note_tail = (
        " · เป็นข้อเสนอจากหลักเกณฑ์ ไม่ใช่ผลการจัดประเภท "
        "ต้องอ่านคู่มือหลักเกณฑ์การจัดประเภทเครื่องมือแพทย์ตามความเสี่ยงประกอบ"
    )

    if role == "control":
        return 3, "ข้อ 9(2)", (
            "ควบคุมหรือติดตามเครื่องมือแพทย์ จนมีผลโดยตรงต่อสมรรถนะของเครื่องนั้น"
            + note_tail
        )
    if role == "inform":
        if critical:
            return 2, "ข้อ 10(1)", "ให้ข้อมูลทางคลินิกของโรคที่วิกฤตอันตรายร้ายแรง" + note_tail
        return 1, "ข้อ 12", "ให้ข้อมูลทางคลินิกของโรคที่ไม่วิกฤตอันตรายร้ายแรงหรือถึงแก่ชีวิต" + note_tail
    if role == "drive":
        if critical:
            return 3, "ข้อ 10(1)", (
                "วินิจฉัย วางแผนการรักษา หรือคัดกรองโรคที่วิกฤต ซึ่งอาจทำให้สุขภาพ"
                "เสื่อมอย่างรุนแรง พิการถาวร หรือเสียชีวิต" + note_tail
            )
        return 2, "ข้อ 10(1)", "วินิจฉัย วางแผนการรักษา หรือคัดกรองโรคที่ไม่วิกฤต" + note_tail
    if role == "monitor":
        if critical:
            return 3, "ข้อ 10(1)", (
                "ติดตามเฝ้าระวังค่าทางสรีรวิทยาที่บ่งชี้ภาวะอันตรายเฉียบพลัน" + note_tail
            )
        return 2, "ข้อ 10(1)", "ติดตามกระบวนการทางสรีรวิทยาที่สำคัญต่อชีวิตโดยตรง" + note_tail

    return None, "", "บทบาทที่ระบุไม่ตรงกับหลักเกณฑ์ใด"


def to_dict(db: Session, row: DeviceDetermination) -> dict:
    purposes = _load(row.purposes)
    measures = _load(row.measures_regulated)
    who = None
    if row.assessed_by:
        u = db.query(User).filter(User.id == row.assessed_by).first()
        who = u.username if u else None
    return {
        "id": row.id,
        "app_id": row.app_id,
        "code": row.code,
        "intended_use": row.intended_use or "",
        "target": row.target or "none",
        "purposes": purposes,
        "purpose_labels": [f"({p}) {PURPOSES[p]}" for p in purposes if p in PURPOSES],
        "pharmacological": bool(row.pharmacological),
        "is_accessory": bool(row.is_accessory),
        "disclaims_medical": bool(row.disclaims_medical),
        "measures_regulated": measures,
        "measure_labels": [ALWAYS_REGULATED.get(m, m) for m in measures],
        "verdict": row.verdict.value if hasattr(row.verdict, "value") else str(row.verdict),
        "rationale": row.rationale or "",
        "software_kind": row.software_kind or "",
        "samd_role": row.samd_role or "",
        "samd_condition": row.samd_condition or "",
        "rule_ref": row.rule_ref or "",
        "risk_class": row.risk_class,
        "class_note": row.class_note or "",
        "ruling_requested": bool(row.ruling_requested),
        "ruling_ref": row.ruling_ref or "",
        "assessed_by": who,
        "assessed_at": row.assessed_at.isoformat() if row.assessed_at else None,
    }


def apply_assessment(row: DeviceDetermination, payload: dict, user: User) -> None:
    """เขียนคำตอบลงระเบียน แล้วให้ระบบสรุปผลตามนิยาม"""
    row.intended_use = (payload.get("intended_use") or "")[:5000]
    row.target = payload.get("target") or "none"
    purposes = [p for p in (payload.get("purposes") or []) if p in PURPOSES]
    measures = [m for m in (payload.get("measures_regulated") or []) if m in ALWAYS_REGULATED]
    row.purposes = json.dumps(purposes, ensure_ascii=False)
    row.measures_regulated = json.dumps(measures, ensure_ascii=False)
    row.pharmacological = bool(payload.get("pharmacological"))
    row.is_accessory = bool(payload.get("is_accessory"))
    row.disclaims_medical = bool(payload.get("disclaims_medical"))

    verdict, why = decide(
        row.target, purposes, row.pharmacological,
        row.is_accessory, row.disclaims_medical, measures,
    )
    row.verdict = verdict

    extra = (payload.get("rationale") or "").strip()
    lines = list(why)
    if extra:
        lines.append(f"บันทึกเพิ่มเติมโดยผู้ประเมิน: {extra}")
    row.rationale = "\n".join(lines)[:5000]

    row.software_kind = payload.get("software_kind") or ""
    row.samd_role = payload.get("samd_role") or ""
    row.samd_condition = payload.get("samd_condition") or ""

    if verdict in (DeviceVerdict.IS_DEVICE, DeviceVerdict.ACCESSORY):
        cls, rule, note = classify_samd(
            row.software_kind, row.samd_role, row.samd_condition, purposes)
        # ค่าที่ผู้ประเมินระบุเองชนะข้อเสนอของระบบเสมอ — ระบบเสนอ คนตัดสิน
        row.risk_class = payload.get("risk_class") or cls
        row.rule_ref = rule
        row.class_note = note
    else:
        row.risk_class = None
        row.rule_ref = ""
        row.class_note = ""

    row.ruling_requested = bool(payload.get("ruling_requested"))
    row.ruling_ref = (payload.get("ruling_ref") or "")[:120]
    row.assessed_by = user.id
    row.assessed_at = datetime.utcnow()


# เอกสารที่ต้องยื่นตามช่องทาง — จากเอกสารแนวทางการขึ้นทะเบียน SaMD
LISTING_DOCS = [
    "ฉลากเครื่องมือแพทย์ (Device Labelling)",
    "เอกสารกำกับเครื่องมือแพทย์ (ถ้ามี)",
    "ข้อกำหนดเฉพาะของเครื่องมือแพทย์ (Product Specification)",
    "รายละเอียดและสมบัติของวัสดุที่ใช้ผลิตหรือเป็นส่วนประกอบ",
    "ลักษณะทั่วไปและหลักการทำงาน (Device Description and Features)",
    "Declaration of conformity",
]
CSDT_DOCS = [
    "ฉลากและเอกสารกำกับเครื่องมือแพทย์",
    "บทสรุปเกี่ยวกับเครื่องมือแพทย์ และรายละเอียดเครื่องมือแพทย์",
    "Essential Principles",
    "Summary Verification & Validation (ช่องทาง Full)",
    "เอกสารแสดงการวิเคราะห์ความเสี่ยง (ช่องทาง Full)",
    "ข้อมูลผู้ผลิตและสถานที่ผลิต",
    "หนังสือรับรองระบบคุณภาพ ISO/GMP",
    "Declaration of conformity",
]
# ฉลากซอฟต์แวร์ต้องมีอย่างน้อยแปดรายการ ตามประกาศกระทรวงสาธารณสุข พ.ศ. 2568
LABEL_ITEMS = [
    "ชื่อผลิตภัณฑ์", "วัตถุประสงค์การใช้", "ข้อบ่งใช้",
    "รายละเอียดเกี่ยวกับเครื่องมือแพทย์ที่จำเป็น",
    "ชื่อของผู้ผลิตหรือเจ้าของผลิตภัณฑ์",
    "เลขแสดงเวอร์ชัน เลขแสดงครั้งที่ผลิต รุ่นที่ผลิต หรือรหัสประจำเครื่อง",
    "คำเตือน ข้อห้ามใช้ หรือข้อควรระวัง (ถ้ามี)", "UDI (ถ้ามี)",
]


def next_steps(verdict: str, risk_class: Optional[int]) -> List[str]:
    """สิ่งที่ต้องทำต่อ ตามผลการวินิจฉัย — ตามลำดับที่ อย. วางไว้"""
    if verdict == "not_device":
        return [
            "ไม่ต้องขึ้นทะเบียนเป็นเครื่องมือแพทย์",
            "ห้ามโฆษณาหรือระบุสรรพคุณในทางการแพทย์ เพราะจะทำให้เข้าข่ายทันที",
            "ทบทวนผลนี้ใหม่ทุกครั้งที่เปลี่ยนวัตถุประสงค์การใช้งาน",
        ]
    if verdict == "needs_ruling":
        return [
            "ยื่นขอคำวินิจฉัยผลิตภัณฑ์จากกองควบคุมเครื่องมือแพทย์ อย.",
            "ระงับการนำออกจำหน่ายไว้ก่อนจนกว่าจะได้ข้อยุติ",
        ]
    steps = [
        "จัดทำระบบบริหารคุณภาพตาม ISO 13485:2016",
        "จัดการความเสี่ยงตาม ISO 14971:2019 ตลอดวงจรชีวิต",
        "ทำการควบคุมการออกแบบให้ครบ — ปัจจัยนำเข้า ผลลัพธ์ ทวนสอบ ตรวจสอบความใช้ได้ ถ่ายทอด",
        "จัดทำฉลากและเอกสารกำกับตามประกาศกระทรวงสาธารณสุข พ.ศ. 2568 "
        f"({len(LABEL_ITEMS)} รายการขั้นต่ำ) อ้างอิง ISO 20417 และ ISO 15223",
        "จดทะเบียนสถานประกอบการเครื่องมือแพทย์กับ อย.",
    ]
    if risk_class == 1:
        steps.append(
            f"ขึ้นทะเบียนแบบจดแจ้ง (Listing) — ใบรับจดแจ้ง · เอกสารหลักประมาณ {len(LISTING_DOCS)} รายการ"
        )
    elif risk_class in (2, 3):
        steps.append(
            "ขึ้นทะเบียนแบบแจ้งรายการละเอียด — ใบรับแจ้งรายการละเอียด · "
            "จัดทำเอกสารรูปแบบ ASEAN CSDT (เลือกช่องทาง Full หรือ Abridged)"
        )
    elif risk_class == 4:
        steps.append("ขึ้นทะเบียนแบบขออนุญาต — ใบอนุญาต · จัดทำเอกสารรูปแบบ ASEAN CSDT")
    else:
        steps.append("จัดระดับความเสี่ยงให้ได้ข้อยุติ เพื่อกำหนดช่องทางการขึ้นทะเบียน")
    steps.append("ยื่นผ่านระบบ e-Submission ของ อย.")
    return steps


def required_docs(risk_class: Optional[int]) -> List[str]:
    if risk_class == 1:
        return LISTING_DOCS
    if risk_class in (2, 3, 4):
        return CSDT_DOCS
    return []


def gaps_for_app(db: Session, app_id: int) -> dict:
    """ช่องว่างด้านการวินิจฉัยผลิตภัณฑ์ สำหรับรวมเข้าตารางตามรอย"""
    rows = db.query(DeviceDetermination).filter(
        DeviceDetermination.app_id == app_id).all()
    if not rows:
        return {"device_unassessed": ["ยังไม่ได้วินิจฉัยว่าเข้าข่ายเครื่องมือแพทย์หรือไม่"]}

    unassessed, needs_ruling, unclassified = [], [], []
    for r in rows:
        v = r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict)
        if v == "unassessed":
            unassessed.append(r.code)
        if v == "needs_ruling" and not r.ruling_requested:
            needs_ruling.append(r.code)
        if v in ("is_device", "accessory") and not r.risk_class:
            unclassified.append(r.code)
    return {
        "device_unassessed": sorted(unassessed),
        "device_needs_ruling": sorted(needs_ruling),
        "device_unclassified": sorted(unclassified),
    }
