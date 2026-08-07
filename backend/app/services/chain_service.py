"""
Evidence chain — โซ่หลักฐานของสัญญาอิเล็กทรอนิกส์หนึ่งฉบับ

ทำไมต้องมี: ม.11 กำหนดว่าการชั่งน้ำหนักพยานหลักฐานอิเล็กทรอนิกส์ให้พิเคราะห์ถึง
"ความน่าเชื่อถือของลักษณะหรือวิธีการที่ใช้สร้าง เก็บรักษา หรือสื่อสาร" และ "ความครบถ้วน
และไม่มีการเปลี่ยนแปลงของข้อความ" — การเก็บ hash ของเอกสารอย่างเดียวพิสูจน์ได้แค่ว่า
*เนื้อหา* ไม่ถูกแก้ แต่พิสูจน์ไม่ได้ว่า *ลำดับเหตุการณ์* ไม่ถูกสลับหรือข้าม

โซ่นี้ผูกแต่ละเหตุการณ์เข้ากับเหตุการณ์ก่อนหน้า:

    chain_hash(n) = SHA256("ivs-econtract-v1|n|step|chain_hash(n-1)|payload_hash(n)")

การแก้เหตุการณ์ใดเหตุการณ์หนึ่งจะทำให้ chain_hash ของทุกเหตุการณ์หลังจากนั้นเปลี่ยน
และหัวโซ่ถูกผูกด้วย HMAC ของเครื่อง จึงตรวจพบได้

**สิ่งที่โซ่นี้พิสูจน์ไม่ได้** (ต้องพูดให้ตรงเวลานำเสนอ):
- ไม่ได้พิสูจน์ว่าเจ้าของลายเซ็นเป็นใครจริง ๆ — ขึ้นกับระดับการยืนยันตัวตนที่ใช้
- ไม่ได้พิสูจน์ว่าเครื่องนี้ไม่ได้สร้างโซ่ปลอมทั้งชุด — ใครมี SECRET_KEY ทำได้
  (นี่คือเหตุผลที่ยังเป็น ม.9 ไม่ใช่ ม.26 ต้องรอ PAdES + ใบรับรองจาก CA)
- เวลาเป็นเวลาที่เครื่องนี้บันทึกโดยอ้างอิง NTP ราชการ ไม่ใช่เวลาที่บุคคลที่สามยืนยัน
  (ต้องรอ RFC 3161 TSA)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import unicodedata
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings

# ขึ้นเวอร์ชันเมื่อรูปแบบ canonical หรือสูตร hash เปลี่ยน — โซ่เก่าต้องยังตรวจได้ด้วย
# สูตรเดิม จึงเก็บเวอร์ชันไว้ในทุก link
CHAIN_VERSION = "ivs-econtract-v1"
GENESIS = "0" * 64

# ลำดับเหตุการณ์ที่รองรับ
STEP_DOCUMENT = "document"           # ออกใบรับรองร่าง (H0)
STEP_DELIVER = "deliver"             # ส่งร่างให้คู่สัญญา + บันทึกการส่ง
STEP_ACCEPTANCE = "offer_acceptance"  # คำเสนอ–คำสนองตรงกัน (ม.13)
STEP_SIGN = "sign"                   # ลงลายมือชื่อ (ม.9/26) — ตราประทับอยู่ในขั้นนี้
STEP_SEAL = "seal"                   # ประทับตรานิติบุคคล (ม.9 วรรคท้าย)
STEP_ORIGINAL = "original"           # ตรึงต้นฉบับ (ม.10) ← จุดล็อก
STEP_STAMP_DUTY = "stamp_duty"       # อากรแสตมป์ (ม.8 ว.2)
STEP_RETENTION = "retention"         # แถลงการเก็บรักษา (ม.12)
STEP_PRINT_OUT = "print_out"         # สิ่งพิมพ์ออก (ม.10 ว.4)
STEP_AMENDMENT = "amendment"         # แก้ไขหลังลงนาม (FAQ eSignature ข้อ 5)

# ขั้นตอนที่ต้องทำ "ก่อน" ตรึงต้นฉบับ — เพราะเป็นส่วนที่ประกอบขึ้นเป็นตัวสัญญา
PRE_LOCK_STEPS = {STEP_DOCUMENT, STEP_DELIVER, STEP_ACCEPTANCE, STEP_SIGN, STEP_SEAL}

# ขั้นตอนที่ผนวกได้ "หลัง" ตรึงต้นฉบับ — เป็นเอกสารประกอบที่อ้างถึงต้นฉบับ ไม่ใช่ตัวต้นฉบับ
# (อากรแสตมป์ต้องชำระหลังตราสารสมบูรณ์ และมีกำหนดเวลา จึงเป็นไปไม่ได้ที่จะรู้ตอนตรึง)
POST_LOCK_STEPS = {STEP_STAMP_DUTY, STEP_RETENTION, STEP_PRINT_OUT, STEP_AMENDMENT}

STEP_LABELS = {
    STEP_DOCUMENT:   {"th": "จัดทำร่างเป็นข้อมูลอิเล็กทรอนิกส์", "sections": ["8"]},
    STEP_DELIVER:    {"th": "ส่งร่างให้คู่สัญญา และบันทึกการส่ง", "sections": ["12"]},
    STEP_ACCEPTANCE: {"th": "คำเสนอและคำสนองตรงกัน", "sections": ["13"]},
    STEP_SIGN:       {"th": "ลงลายมือชื่ออิเล็กทรอนิกส์", "sections": ["9", "26"]},
    STEP_SEAL:       {"th": "ประทับตรานิติบุคคล", "sections": ["9 วรรคท้าย"]},
    STEP_ORIGINAL:   {"th": "ตรึงต้นฉบับ", "sections": ["10"]},
    STEP_STAMP_DUTY: {"th": "ชำระอากรแสตมป์", "sections": ["8 วรรคสอง"]},
    STEP_RETENTION:  {"th": "แถลงการเก็บรักษา", "sections": ["11", "12"]},
    STEP_PRINT_OUT:  {"th": "จัดทำสิ่งพิมพ์ออก", "sections": ["10 วรรค 4"]},
    STEP_AMENDMENT:  {"th": "แก้ไขหลังลงนาม", "sections": ["10"]},
}


class ChainError(ValueError):
    """โซ่ถูกใช้ผิดลำดับ หรือพยายามแก้สิ่งที่ตรึงแล้ว"""


# ── Canonical serialisation ──────────────────────────────────────────────
#
# ต้องนิ่งตลอดกาล: ถ้ารูปแบบเปลี่ยน โซ่ที่สร้างไว้แล้วจะ verify ไม่ผ่านตลอดไป
# กฎที่ยึด:
#   - JSON คีย์เรียงเสมอ ไม่มีช่องว่าง
#   - ข้อความ normalize NFC (ภาษาไทยมีได้ทั้ง NFC/NFD ซึ่ง byte ต่างกัน)
#   - เวลาเป็น ISO-8601 UTC มี timezone เสมอ ความละเอียดไมโครวินาที
#     (naive datetime ถือเป็น UTC — SQLite คืนค่าแบบ naive)
#   - ไบต์เป็น base64 มาตรฐาน คง padding
#   - float ไม่รับ เพราะ repr ไม่การันตีข้ามแพลตฟอร์ม

def _norm(v):
    if v is None or isinstance(v, (bool, int)):
        return v
    if isinstance(v, float):
        raise ChainError("canonical form ไม่รับ float — ให้ใช้ str หรือ int แทน")
    if isinstance(v, str):
        return unicodedata.normalize("NFC", v)
    if isinstance(v, bytes):
        return base64.b64encode(v).decode("ascii")
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    if isinstance(v, dict):
        return {unicodedata.normalize("NFC", str(k)): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return unicodedata.normalize("NFC", str(v))


def canonical(obj) -> bytes:
    """ไบต์ที่ใช้คำนวณ hash — deterministic ข้ามเครื่องและข้ามเวอร์ชัน Python"""
    return json.dumps(
        _norm(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def payload_digest(payload) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def link_hash(seq: int, step: str, prev_hash: str, payload_hash: str) -> str:
    """ผูก seq และ step เข้าไปด้วย เพื่อกันการสลับลำดับหรือเปลี่ยนชื่อขั้นตอน"""
    msg = f"{CHAIN_VERSION}|{seq}|{step}|{prev_hash}|{payload_hash}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def head_signature(chain_hash: str) -> str:
    """ลายเซ็นระบบบนหัวโซ่ — ยืนยันว่าโซ่นี้ออกโดย iVS เครื่องนี้ (ม.9)"""
    return hmac.new(
        settings.SECRET_KEY.encode(), f"{CHAIN_VERSION}|{chain_hash}".encode(),
        hashlib.sha256,
    ).hexdigest()


# ── การเขียนโซ่ ──────────────────────────────────────────────────────────

def _links(db: Session, cert_id: str):
    from app.models import EContractChainLink
    return (
        db.query(EContractChainLink)
        .filter(EContractChainLink.cert_id == cert_id)
        .order_by(EContractChainLink.seq.asc())
        .all()
    )


def head(db: Session, cert_id: str):
    from app.models import EContractChainLink
    return (
        db.query(EContractChainLink)
        .filter(EContractChainLink.cert_id == cert_id)
        .order_by(EContractChainLink.seq.desc())
        .first()
    )


def is_locked(db: Session, cert_id: str) -> bool:
    """ตรึงต้นฉบับแล้วหรือยัง — ถ้าแล้ว ห้ามเพิ่มขั้นตอนที่ประกอบเป็นตัวสัญญาอีก"""
    from app.models import EContractChainLink
    return (
        db.query(EContractChainLink)
        .filter(EContractChainLink.cert_id == cert_id,
                EContractChainLink.step == STEP_ORIGINAL)
        .first()
        is not None
    )


def append(db: Session, cert_id: str, step: str, payload: dict,
           created_by: int = None, commit: bool = True) -> dict:
    """ต่อเหตุการณ์หนึ่งเข้าโซ่

    ปฏิเสธเมื่อพยายามเพิ่มขั้นตอนที่ประกอบเป็นตัวสัญญาหลังตรึงต้นฉบับแล้ว — ม.10
    กำหนดว่าต้นฉบับต้อง "ไม่มีการเปลี่ยนแปลงแก้ไขนับแต่สร้างเสร็จสมบูรณ์"
    """
    from app.models import EContractChainLink
    from app.services.ntp_service import ntp_service

    if step not in STEP_LABELS:
        raise ChainError(f"ไม่รู้จักขั้นตอน: {step}")

    locked = is_locked(db, cert_id)
    if locked and step in PRE_LOCK_STEPS:
        raise ChainError(
            f"ตรึงต้นฉบับแล้ว จึงเพิ่มขั้นตอน '{STEP_LABELS[step]['th']}' ไม่ได้ "
            "— ม.10 กำหนดให้ต้นฉบับต้องไม่มีการเปลี่ยนแปลงนับแต่สร้างเสร็จสมบูรณ์ "
            "(ถ้าต้องแก้ไขจริง ให้ทำเป็นฉบับแก้ไขที่อ้างถึงฉบับนี้)"
        )
    if step == STEP_ORIGINAL and locked:
        raise ChainError("ตรึงต้นฉบับไปแล้ว ทำซ้ำไม่ได้")

    prev = head(db, cert_id)
    seq = (prev.seq + 1) if prev else 0
    prev_hash = prev.chain_hash if prev else GENESIS
    if seq == 0 and step != STEP_DOCUMENT:
        raise ChainError("เหตุการณ์แรกของโซ่ต้องเป็นการจัดทำร่าง (document)")

    now = ntp_service.now()
    ntp = ntp_service.get_status()
    body = {
        "step": step,
        "cert_id": cert_id,
        "recorded_at": now,
        "ntp_server": ntp.get("ntp_server") or "",
        "ntp_server_name": ntp.get("ntp_server_name") or "",
        "data": payload,
    }
    ph = payload_digest(body)
    ch = link_hash(seq, step, prev_hash, ph)

    row = EContractChainLink(
        cert_id=cert_id, seq=seq, step=step, version=CHAIN_VERSION,
        prev_hash=prev_hash, payload_hash=ph, chain_hash=ch,
        payload_json=canonical(body).decode("utf-8"),
        ntp_time=now, created_by=created_by,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return to_dict(row)


def to_dict(row) -> dict:
    try:
        payload = json.loads(row.payload_json) if row.payload_json else {}
    except Exception:
        payload = {}
    meta = STEP_LABELS.get(row.step, {})
    return {
        "seq": row.seq,
        "step": row.step,
        "step_th": meta.get("th", row.step),
        "sections": meta.get("sections", []),
        "version": row.version,
        "prev_hash": row.prev_hash,
        "payload_hash": row.payload_hash,
        "chain_hash": row.chain_hash,
        "recorded_at": row.ntp_time.isoformat() if row.ntp_time else None,
        "payload": payload.get("data", {}),
        "ntp_server_name": payload.get("ntp_server_name", ""),
        "post_lock": row.step in POST_LOCK_STEPS,
    }


# ── การตรวจสอบโซ่ ────────────────────────────────────────────────────────

def verify(db: Session, cert_id: str) -> dict:
    """เดินโซ่ตั้งแต่ต้น คำนวณใหม่ทุก link แล้วเทียบกับที่บันทึกไว้

    คืนตำแหน่งแรกที่ผิดพลาด เพื่อให้รู้ว่าถูกแก้ตรงไหน ไม่ใช่แค่บอกว่าพัง
    """
    rows = _links(db, cert_id)
    if not rows:
        return {"valid": False, "reason_th": "ยังไม่มีโซ่หลักฐานสำหรับใบรับรองนี้",
                "length": 0, "broken_at": None, "head_hash": "", "head_signature_valid": False}

    prev_hash = GENESIS
    for i, r in enumerate(rows):
        if r.seq != i:
            return {"valid": False, "reason_th": f"ลำดับขาดหายที่ตำแหน่ง {i} (พบ seq={r.seq})",
                    "length": len(rows), "broken_at": i, "head_hash": "",
                    "head_signature_valid": False}
        if r.prev_hash != prev_hash:
            return {"valid": False,
                    "reason_th": f"link ที่ {i} ({STEP_LABELS.get(r.step, {}).get('th', r.step)}) "
                                 "ไม่ได้ต่อจาก link ก่อนหน้า — โซ่ถูกตัดหรือแทรก",
                    "length": len(rows), "broken_at": i, "head_hash": "",
                    "head_signature_valid": False}
        expect_payload = hashlib.sha256(r.payload_json.encode("utf-8")).hexdigest()
        if expect_payload != r.payload_hash:
            return {"valid": False,
                    "reason_th": f"เนื้อหาของ link ที่ {i} "
                                 f"({STEP_LABELS.get(r.step, {}).get('th', r.step)}) ถูกแก้ไข",
                    "length": len(rows), "broken_at": i, "head_hash": "",
                    "head_signature_valid": False}
        expect_chain = link_hash(r.seq, r.step, r.prev_hash, r.payload_hash)
        if expect_chain != r.chain_hash:
            return {"valid": False,
                    "reason_th": f"ค่า hash ของ link ที่ {i} ไม่ตรงกับที่คำนวณได้",
                    "length": len(rows), "broken_at": i, "head_hash": "",
                    "head_signature_valid": False}
        prev_hash = r.chain_hash

    return {
        "valid": True,
        "reason_th": f"โซ่หลักฐานครบถ้วน {len(rows)} เหตุการณ์ ต่อเนื่องและไม่ถูกแก้ไข",
        "length": len(rows),
        "broken_at": None,
        "head_hash": prev_hash,
        "head_signature": head_signature(prev_hash),
        "head_signature_valid": True,
        "locked": is_locked(db, cert_id),
    }


def chain(db: Session, cert_id: str) -> dict:
    rows = _links(db, cert_id)
    return {
        "cert_id": cert_id,
        "version": CHAIN_VERSION,
        "links": [to_dict(r) for r in rows],
        "verification": verify(db, cert_id),
    }
