"""
e-Contract Timestamp & Integrity Certificate service.

Backbone for electronic-transaction evidence under Thailand's Electronic
Transactions Act (ธุรกรรมทางอิเล็กทรอนิกส์): document **integrity** (§12) via a
SHA-256 fingerprint, a **trusted timestamp** from the Thai legal NTP servers,
and a machine signature (HMAC keyed by the instance SECRET_KEY) that lets
anyone verify the certificate was issued by this iVS and has not been altered.

All processing is local — no external CA/TSA call — so it fits iVS's data
sovereignty stance. (A future phase can add certificate-authority-backed
digital signatures for the highest legal tier.)
"""
import hashlib
import hmac
import io
import json
import secrets
import zipfile
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EContractCert, EContractSignature
from app.services.ntp_service import ntp_service


def _sign(sha256: str, ntp_iso: str) -> str:
    """HMAC-SHA256(sha256 | ntp_time) with the instance SECRET_KEY."""
    msg = f"{sha256}|{ntp_iso}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _cert_id() -> str:
    return "ECT-" + secrets.token_hex(8).upper()


def certify(db: Session, filename: str, data: bytes, signer: str = "",
            note: str = "", created_by: int = None,
            profile_key: str = "generic", sector: str = "") -> dict:
    """Issue an integrity + trusted-timestamp certificate for `data`.

    `profile_key` เลือกโปรไฟล์ 7 เรื่อง (ดู profile_service) — โปรไฟล์ที่ resolve ได้จะถูก
    **แช่แข็ง** ไว้กับใบรับรอง เพื่อให้สัญญาถูกประเมินด้วยกฎชุดเดิมตลอดอายุความ
    """
    from app.services import profile_service
    from app.services.compliance_service import detect_doc_format

    eff = profile_service.resolve(profile_key or "generic", sector=sector or None)
    if eff.get("blocked"):
        raise ValueError(
            f"{eff.get('name_th', profile_key)} — {eff.get('blocked_reason_th', 'ทำเป็นอิเล็กทรอนิกส์ไม่ได้')}"
        )

    sha256 = hashlib.sha256(data).hexdigest()
    now = ntp_service.now()
    ntp = ntp_service.get_status()

    row = EContractCert(
        cert_id=_cert_id(),
        filename=filename[:400],
        size_bytes=len(data),
        sha256=sha256,
        ntp_time=now,
        ntp_server=ntp.get("ntp_server") or "",
        ntp_server_name=ntp.get("ntp_server_name") or "",
        signature="",  # set after the DB round-trip (see below)
        signer=signer[:120],
        note=note or "",
        created_by=created_by,
        profile_key=eff.get("key", "generic"),
        profile_version=int(eff.get("version", 1)),
        profile_sector=sector or "",
        effective_profile_json=json.dumps(eff, ensure_ascii=False),
        effective_profile_hash=eff.get("_hash", ""),
        doc_format=detect_doc_format(data, filename),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    # Sign AFTER the round-trip so the signed timestamp string is exactly what
    # verify() will read back from the DB (SQLite returns a naive datetime;
    # signing the persisted value keeps certify and verify byte-identical).
    row.signature = _sign(row.sha256, row.ntp_time.isoformat())
    db.commit()
    db.refresh(row)

    # เหตุการณ์แรกของโซ่หลักฐาน (H0)
    from app.services import chain_service
    chain_service.append(db, row.cert_id, chain_service.STEP_DOCUMENT, {
        "filename": row.filename,
        "sha256": row.sha256,
        "size_bytes": row.size_bytes,
        "doc_format": row.doc_format,
        "profile_key": row.profile_key,
        "profile_version": row.profile_version,
        "profile_hash": row.effective_profile_hash,
        "sector": row.profile_sector,
        "issued_by": signer or "",
    }, created_by=created_by)
    return to_dict(row)


def verify(db: Session, sha256: str = "", signature: str = "",
           cert_id: str = "") -> dict:
    """Verify a certificate. Match by cert_id or sha256, then re-check the
    signature. Returns {valid, reason, cert}."""
    q = db.query(EContractCert)
    row = None
    if cert_id:
        row = q.filter(EContractCert.cert_id == cert_id).first()
    elif sha256:
        row = q.filter(EContractCert.sha256 == sha256).first()
    if not row:
        return {"valid": False, "reason": "ไม่พบใบรับรองสำหรับเอกสารนี้", "cert": None}

    expected = _sign(row.sha256, row.ntp_time.isoformat())
    sig_ok = hmac.compare_digest(expected, row.signature)
    hash_ok = (not sha256) or (sha256 == row.sha256)

    if not sig_ok:
        return {"valid": False, "reason": "ลายเซ็นไม่ถูกต้อง (ใบรับรองอาจถูกแก้ไข)", "cert": to_dict(row)}
    if not hash_ok:
        return {"valid": False, "reason": "ลายนิ้วมือเอกสารไม่ตรง (เนื้อหาถูกแก้ไข)", "cert": to_dict(row)}
    return {"valid": True, "reason": "ถูกต้อง — เอกสารครบถ้วนและออกโดย iVS เครื่องนี้", "cert": to_dict(row)}


def to_dict(row: EContractCert) -> dict:
    return {
        "id": row.id,
        "cert_id": row.cert_id,
        "filename": row.filename,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "ntp_time": row.ntp_time.isoformat() if row.ntp_time else None,
        "ntp_server": row.ntp_server,
        "ntp_server_name": row.ntp_server_name,
        "signature": row.signature,
        "signer": row.signer,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "profile_key": row.profile_key or "generic",
        "profile_version": row.profile_version or 1,
        "profile_sector": row.profile_sector or "",
        "profile_hash": row.effective_profile_hash or "",
        "doc_format": row.doc_format or "",
    }


# ── e-Signature (Phase 2) ────────────────────────────────────────────────

def _sign_signature(cert_sha256: str, signer: str, signed_iso: str, method: str) -> str:
    msg = f"{cert_sha256}|{signer}|{signed_iso}|{method}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def sig_to_dict(s: EContractSignature) -> dict:
    return {
        "id": s.id,
        "cert_id": s.cert_id,
        "signer_name": s.signer_name,
        "signer_role": s.signer_role or "",
        "method": s.method,
        "identity_ref": s.identity_ref,
        "signed_at": s.signed_at.isoformat() if s.signed_at else None,
        "ip_address": s.ip_address,
        "signature": s.signature,
    }


def add_signature(db: Session, cert_id: str, signer_name: str, method: str = "typed",
                  identity_ref: str = "", ip: str = "", created_by: int = None,
                  signing_mode: str = "remote", user_agent: str = "",
                  signer_role: str = "") -> dict:
    """Record an electronic signature on a certificate (§9/§26).

    `signing_mode` แยกการลงนามต่อหน้าบนเครื่องของหน่วยงานออกจากการลงนามระยะไกล —
    กรณีต่อหน้า IP ที่บันทึกได้เป็นของหน่วยงาน ไม่ได้พิสูจน์ตัวคู่สัญญา จึงบันทึกผู้ควบคุม
    เครื่องไว้ด้วยเพื่อให้ผู้ชั่งน้ำหนักพยานหลักฐาน (ม.11) ตัดสินได้เอง
    """
    from app.services import chain_service

    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    if chain_service.is_locked(db, cert_id):
        raise ValueError(
            "ตรึงต้นฉบับแล้ว จึงลงนามเพิ่มไม่ได้ — ม.10 กำหนดให้ต้นฉบับต้องไม่มีการ"
            "เปลี่ยนแปลงนับแต่สร้างเสร็จสมบูรณ์"
        )
    mode = signing_mode if signing_mode in ("in_person", "remote") else "remote"
    now = ntp_service.now()
    row = EContractSignature(
        cert_id=cert_id, signer_name=signer_name[:200],
        signer_role=(signer_role or "")[:120],
        method=method if method in ("typed", "drawn", "otp") else "typed",
        identity_ref=(identity_ref or "")[:300000], signed_at=now,  # allow a drawn-signature PNG data URI
        ip_address=(ip or "")[:45], signature="", created_by=created_by,
        signing_mode=mode,
        # ผู้ควบคุมเครื่องมีความหมายเฉพาะกรณีลงนามต่อหน้า
        operator_user_id=created_by if mode == "in_person" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.signature = _sign_signature(cert.sha256, row.signer_name, row.signed_at.isoformat(), row.method)
    db.commit()
    db.refresh(row)

    # อีเมลที่ใช้ลงนามควรเป็นอีเมลเดียวกับที่ส่งร่างไป — ถ้าไม่ตรง โซ่การระบุตัวตนขาด
    # ระบบไม่ห้าม (บางกรณีมีเหตุผล) แต่ต้องบันทึกไว้ให้เห็นชัดในหลักฐาน
    delivered = chain_service.delivered_recipients(db, cert_id)
    ident = (identity_ref or "").strip().lower()
    matches = bool(delivered) and ident in [d.strip().lower() for d in delivered]

    from app.services.compliance_service import METHOD_ASSURANCE
    chain_service.append(db, cert_id, chain_service.STEP_SIGN, {
        "signer_name": row.signer_name,
        "signer_role": row.signer_role,
        "method": row.method,
        "assurance_level": METHOD_ASSURANCE.get(row.method, "general"),
        "signing_mode": row.signing_mode,
        "operator_user_id": row.operator_user_id,
        "identity_evidence": _identity_summary(row),
        "identity_matches_delivery": matches,
        "delivered_recipients": delivered,
        "ip_address": row.ip_address,
        "user_agent": (user_agent or "")[:300],
        "signed_at": row.signed_at,
        "signature_hmac": row.signature,
    }, created_by=created_by)
    out = sig_to_dict(row)
    out["identity_matches_delivery"] = matches
    out["delivered_recipients"] = delivered
    return out


def _identity_summary(row) -> str:
    """สรุปหลักฐานตัวตนโดยไม่เอาภาพลายเซ็นทั้งก้อนเข้าโซ่ (data URI ยาวมาก)"""
    ref = row.identity_ref or ""
    if ref.startswith("data:image"):
        return "drawn-signature-image:sha256=" + hashlib.sha256(ref.encode()).hexdigest()
    return ref[:200]


def list_signatures(db: Session, cert_id: str) -> list:
    rows = db.query(EContractSignature).filter(EContractSignature.cert_id == cert_id).order_by(EContractSignature.signed_at.asc()).all()
    return [sig_to_dict(r) for r in rows]


def detail(db: Session, cert_id: str) -> dict:
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        return None
    d = to_dict(cert)
    d["signatures"] = list_signatures(db, cert_id)
    try:
        from app.services import compliance_service
        d["compliance"] = compliance_service.evaluate(db, cert)
    except Exception as e:  # การประเมินล้มเหลวต้องไม่ทำให้ดูใบรับรองไม่ได้
        import logging
        logging.getLogger(__name__).warning(f"ประเมิน 7 ขั้นตอนของ {cert_id} ไม่สำเร็จ: {e}")
        d["compliance"] = None
    return d


# ── e-Seal — ตราประทับนิติบุคคล (ม.9 วรรคท้าย) ───────────────────────────

MAX_SEAL_IMAGE = 400_000  # ~300 KB หลัง base64


def seal_to_dict(s) -> dict:
    return {
        "seal_id": s.seal_id,
        "org_name": s.org_name,
        "org_tax_id": s.org_tax_id,
        "image_data": s.image_data,
        "authority_note": s.authority_note,
        "is_active": bool(s.is_active),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def list_seals(db: Session, include_inactive: bool = False) -> list:
    from app.models import EContractSeal
    q = db.query(EContractSeal)
    if not include_inactive:
        q = q.filter(EContractSeal.is_active == True)  # noqa: E712
    return [seal_to_dict(s) for s in q.order_by(EContractSeal.created_at.desc()).all()]


def create_seal(db: Session, org_name: str, org_tax_id: str = "", image_data: str = "",
                authority_note: str = "", created_by: int = None) -> dict:
    from app.models import EContractSeal
    if not org_name.strip():
        raise ValueError("ต้องระบุชื่อนิติบุคคล")
    if image_data and len(image_data) > MAX_SEAL_IMAGE:
        raise ValueError("ภาพตราประทับใหญ่เกินไป (จำกัด ~300 KB)")
    row = EContractSeal(
        seal_id="SEAL-" + secrets.token_hex(5).upper(),
        org_name=org_name.strip()[:200],
        org_tax_id=(org_tax_id or "").strip()[:20],
        image_data=image_data or "",
        authority_note=authority_note or "",
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return seal_to_dict(row)


def deactivate_seal(db: Session, seal_id: str) -> dict:
    """เลิกใช้ตรา — ไม่ลบ เพราะสัญญาที่ประทับไปแล้วต้องอ้างอิงกลับได้"""
    from app.models import EContractSeal
    row = db.query(EContractSeal).filter(EContractSeal.seal_id == seal_id).first()
    if not row:
        raise ValueError("ไม่พบตราประทับ")
    row.is_active = False
    db.commit()
    db.refresh(row)
    return seal_to_dict(row)


def apply_seal(db: Session, cert_id: str, seal_id: str, note: str = "",
               applied_by: int = None) -> dict:
    """ประทับตรานิติบุคคลลงบนใบรับรอง แล้วบันทึกเป็นขั้นตอน e_seal

    คู่มือ ETDA ระบุซ้ำในหลายสถานการณ์ว่า "ประทับตรา e-Seal **ควบคู่ไปกับ**ลายมือชื่อ
    อิเล็กทรอนิกส์" — ตราประทับจึงต้องเกิดในช่วงการลงนาม ไม่ใช่หลังตรึงต้นฉบับ
    มิฉะนั้นจะเกิดคำถามว่านิติบุคคลผูกพันตามเอกสาร ณ เวลาใด
    """
    from app.models import EContractSeal
    from app.services import compliance_service, chain_service

    seal = db.query(EContractSeal).filter(EContractSeal.seal_id == seal_id).first()
    if not seal:
        raise ValueError("ไม่พบตราประทับ")
    if not seal.is_active:
        raise ValueError("ตราประทับนี้ถูกเลิกใช้แล้ว")
    if chain_service.is_locked(db, cert_id):
        raise ValueError(
            "ตรึงต้นฉบับแล้ว จึงประทับตราไม่ได้ — คู่มือ ETDA กำหนดให้ประทับตรา"
            "ควบคู่ไปกับการลงลายมือชื่อ ไม่ใช่หลังจากตรึงต้นฉบับ"
        )

    ref = seal.seal_id + (f" · เลขผู้เสียภาษี {seal.org_tax_id}" if seal.org_tax_id else "")
    rec = compliance_service.record_step(
        db, cert_id=cert_id, step_key="e_seal", actor=seal.org_name,
        ref=ref, note=note, status="done",
        detail={"seal_id": seal.seal_id, "org_name": seal.org_name,
                "org_tax_id": seal.org_tax_id, "authority_note": seal.authority_note},
        recorded_by=applied_by,
    )
    chain_service.append(db, cert_id, chain_service.STEP_SEAL, {
        "seal_id": seal.seal_id,
        "org_name": seal.org_name,
        "org_tax_id": seal.org_tax_id,
        "authority_note": seal.authority_note,
        # hash ภาพตรา ให้ตรวจได้ว่าใช้ตราเดียวกัน — แต่ภาพเองไม่ได้พิสูจน์อำนาจ
        # อำนาจมาจากการที่องค์กรควบคุมการใช้ตราและบันทึกไว้ในโซ่นี้
        "image_sha256": hashlib.sha256((seal.image_data or "").encode()).hexdigest(),
        "note": note or "",
    }, created_by=applied_by)
    return rec


# ── ส่งร่าง และคำเสนอ–คำสนอง (ม.13) ─────────────────────────────────────

def record_delivery(db: Session, cert_id: str, recipients: list, channel: str = "email",
                    note: str = "", recorded_by: int = None) -> dict:
    """บันทึกการส่งร่างให้คู่สัญญา

    หมายเหตุ: ขั้นนี้คือ **การส่งไปยังที่อยู่ที่อ้างว่าเป็นของเขา** ไม่ใช่การยืนยันตัวตน
    การพิสูจน์ตัวตนเกิดตอนคู่สัญญากรอก OTP ในขั้นลงนาม ซึ่งพิสูจน์ว่าคุมกล่องจดหมายได้
    """
    from app.services import chain_service
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    clean = [str(r).strip() for r in recipients if str(r).strip()]
    if not clean:
        raise ValueError("ต้องระบุผู้รับอย่างน้อย 1 ราย")
    return chain_service.append(db, cert_id, chain_service.STEP_DELIVER, {
        "channel": channel,
        "doc_sha256": cert.sha256,
        "recipients": clean,
        "recipient_count": len(clean),
        "note": note or "",
        "identity_verified": False,   # ส่งอีเมล ≠ ยืนยันตัวตน
    }, created_by=recorded_by)


def record_acceptance(db: Session, cert_id: str, party: str, source: str = "first_party",
                      evidence: str = "", ip: str = "", note: str = "",
                      recorded_by: int = None, attachment_sha256: str = "",
                      attachment_filename: str = "") -> dict:
    """บันทึกคำสนอง — คู่สัญญาตกลงตามร่างที่เสนอ (ม.13)

    `source` แยกหลักฐานที่ระบบบันทึกเอง (first_party) ออกจากหลักฐานที่นำเข้าจากภายนอก
    (imported) เพราะน้ำหนักต่างกัน — คู่มือ ETDA เตือนว่าภาพหน้าจออย่างเดียวน้ำหนักอ่อน
    ควรประกอบกับ Log หรือพยานแวดล้อม
    """
    from app.services import chain_service
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    if not party.strip():
        raise ValueError("ต้องระบุคู่สัญญาผู้ตอบรับ")
    src = source if source in ("first_party", "imported") else "imported"
    return chain_service.append(db, cert_id, chain_service.STEP_ACCEPTANCE, {
        "party": party.strip(),
        "offer_doc_sha256": cert.sha256,
        "source": src,
        "source_note_th": (
            "ระบบบันทึกเอง — คู่สัญญากดยอมรับในระบบ" if src == "first_party"
            else "นำเข้าจากภายนอก — น้ำหนักขึ้นกับวิธีที่ได้หลักฐานมา"
        ),
        "evidence": (evidence or "")[:2000],
        "evidence_sha256": hashlib.sha256((evidence or "").encode()).hexdigest() if evidence else "",
        "ip_address": (ip or "")[:45],
        "note": note or "",
        "attachment_sha256": attachment_sha256 or "",
        "attachment_filename": attachment_filename or "",
    }, created_by=recorded_by)


# ── ตรึงต้นฉบับ (ม.10) ───────────────────────────────────────────────────

def lock_original(db: Session, cert_id: str, locked_by: int = None) -> dict:
    """ตรึงต้นฉบับ — หลังจากนี้เพิ่มลายเซ็น/ตราประทับไม่ได้อีก

    ตรวจก่อนว่าครบเงื่อนไขของโปรไฟล์หรือยัง (`e_original.lock_on`) เพื่อไม่ให้ตรึง
    เอกสารที่ยังลงนามไม่ครบ ซึ่งจะทำให้ได้ "ต้นฉบับ" ที่ใช้ไม่ได้จริง
    """
    from app.services import chain_service, compliance_service

    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    if chain_service.is_locked(db, cert_id):
        raise ValueError("ตรึงต้นฉบับไปแล้ว")

    prof = compliance_service.effective_profile(cert)
    cfg = (prof.get("steps") or {}).get("e_original") or {}
    sig_cfg = (prof.get("steps") or {}).get("e_signature") or {}
    if cfg.get("lock_on") == "all_parties_signed":
        n = db.query(EContractSignature).filter(EContractSignature.cert_id == cert_id).count()
        need = int(sig_cfg.get("min_signers", 1) or 1)
        if sig_cfg.get("required") and n < need:
            raise ValueError(
                f"ยังลงนามไม่ครบ ({n} จาก {need} ราย) — โปรไฟล์กำหนดให้ตรึงต้นฉบับ"
                "เมื่อลงนามครบทุกฝ่าย"
            )

    now = ntp_service.now()
    ntp = ntp_service.get_status()
    link = chain_service.append(db, cert_id, chain_service.STEP_ORIGINAL, {
        "doc_sha256": cert.sha256,
        "system_signature": cert.signature,
        "timestamp_kind": cfg.get("timestamp", "ntp"),
        "locked_at": now,
        "ntp_server": ntp.get("ntp_server") or "",
        "ntp_server_name": ntp.get("ntp_server_name") or "",
        # เฟส 2 จะเพิ่ม RFC 3161 token จาก TSA ตรงนี้ ซึ่งเป็นเวลาที่บุคคลที่สามยืนยัน
        "tsa_token": None,
    }, created_by=locked_by)

    # วันที่ทำตราสาร ใช้นับกำหนดเวลาเสียอากร — ถ้ายังไม่กำหนดไว้ ให้ยึดวันที่ตรึงต้นฉบับ
    # เพราะเป็นจุดที่ตราสารสมบูรณ์ ไม่ใช่วันที่ออกใบรับรองร่าง
    if not cert.instrument_date:
        cert.instrument_date = now
        db.commit()
    return link


# ── หลักฐานตัวจริง (attachments) + การเลือกเก็บไฟล์ ─────────────────────

import os

ATTACHMENT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "econtract",
)
ATTACHMENT_KINDS = {
    "original_document": "เอกสาร/สัญญาตัวจริง",
    "acceptance_evidence": "หลักฐานคำสนอง",
    "print_out": "สิ่งพิมพ์ออก",
    "other": "หลักฐานอื่น",
}
MAX_ATTACHMENT = 25 * 1024 * 1024


def _safe_name(name: str) -> str:
    keep = "".join(c for c in (name or "file") if c.isalnum() or c in "._- ")
    return (keep.strip() or "file")[:120]


def set_retention_storage(db: Session, cert_id: str, store: bool,
                          changed_by: int = None) -> dict:
    """เปิด/ปิดการเก็บตัวไฟล์จริงของสัญญาฉบับนี้

    ปิดแล้วจะไม่ลบไฟล์ที่เก็บไว้ก่อนหน้า — การลบพยานหลักฐานต้องเป็นการกระทำที่ตั้งใจ
    และแยกต่างหาก ไม่ใช่ผลข้างเคียงของการสลับสวิตช์

    หลังตรึงต้นฉบับ ปิดสวิตช์ไม่ได้ — ปิดแล้วหลักฐานที่แนบต่อจากนี้จะไม่ถูกเก็บ
    ซึ่งเป็นการลดระดับการเก็บรักษาของสัญญาที่สมบูรณ์ไปแล้ว (ม.12) เปิดยังทำได้เสมอ
    เพราะเป็นการยกระดับ
    """
    from app.services import chain_service

    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    if not store and cert.retention_store_files and chain_service.is_locked(db, cert_id):
        raise ValueError(
            "ตรึงต้นฉบับแล้ว จึงปิดการเก็บไฟล์ไม่ได้ — จะทำให้ระดับการเก็บรักษาของสัญญา"
            "ที่สมบูรณ์แล้วลดลง (ม.12) เปิดเพิ่มยังทำได้"
        )
    cert.retention_store_files = bool(store)
    db.commit()
    return {"cert_id": cert_id, "retention_store_files": cert.retention_store_files,
            "locked": chain_service.is_locked(db, cert_id)}


def add_attachment(db: Session, cert_id: str, kind: str, filename: str, data: bytes,
                   content_type: str = "", note: str = "", uploaded_by: int = None,
                   title: str = "") -> dict:
    """แนบหลักฐานตัวจริง — บันทึกลายนิ้วมือเสมอ เก็บไฟล์เมื่อเปิดโหมดเก็บไฟล์"""
    from app.models import EContractAttachment
    from app.services import chain_service

    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    if not data:
        raise ValueError("ไฟล์ว่าง")
    if len(data) > MAX_ATTACHMENT:
        raise ValueError("ไฟล์ใหญ่เกิน 25 MB")
    if kind not in ATTACHMENT_KINDS:
        kind = "other"

    sha = hashlib.sha256(data).hexdigest()

    locked = chain_service.is_locked(db, cert_id)
    if locked and kind == "acceptance_evidence":
        raise ValueError(
            "ตรึงต้นฉบับแล้ว จึงแนบหลักฐานคำสนองไม่ได้ — คำเสนอและคำสนองเป็นส่วนที่"
            "ทำให้สัญญาเกิด (ม.13) ต้องอยู่ก่อนการตรึงต้นฉบับ"
        )
    # เอกสารตัวจริงที่แนบหลังตรึง ต้องเป็นไฟล์เดียวกับที่ออกใบรับรองไว้เป๊ะ ๆ
    # ไม่งั้นจะกลายเป็นการสลับเนื้อหาของสิ่งที่อ้างว่าตรึงแล้ว
    if kind == "original_document" and sha != cert.sha256:
        raise ValueError(
            "ไฟล์ที่แนบไม่ตรงกับเอกสารที่ออกใบรับรองไว้ "
            f"(ใบรับรอง SHA-256 {cert.sha256[:16]}… · ไฟล์นี้ {sha[:16]}…) — "
            "หากเป็นเอกสารคนละฉบับ ให้เลือกประเภทเป็น 'หลักฐานอื่น'"
        )
    row = EContractAttachment(
        cert_id=cert_id, kind=kind, filename=(filename or "file")[:400],
        content_type=(content_type or "")[:120], size_bytes=len(data), sha256=sha,
        stored=False, note=note or "", uploaded_by=uploaded_by,
        title=(title or "")[:300],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if cert.retention_store_files:
        rel = os.path.join(cert_id, f"{row.id}_{_safe_name(filename)}")
        full = os.path.join(ATTACHMENT_ROOT, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        row.stored = True
        row.storage_path = rel
        db.commit()
        db.refresh(row)

    chain_service.append(db, cert_id, chain_service.STEP_ATTACHMENT, {
        "kind": kind,
        "kind_th": ATTACHMENT_KINDS[kind],
        "title": row.title or "",
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "sha256": sha,
        "stored": row.stored,
        "note": note or "",
    }, created_by=uploaded_by)
    return attachment_to_dict(row)


def attachment_to_dict(a) -> dict:
    return {
        "id": a.id,
        "cert_id": a.cert_id,
        "kind": a.kind,
        "kind_th": ATTACHMENT_KINDS.get(a.kind, a.kind),
        "title": a.title or "",
        "filename": a.filename,
        "content_type": a.content_type,
        "size_bytes": a.size_bytes,
        "sha256": a.sha256,
        "stored": bool(a.stored),
        "note": a.note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def list_attachments(db: Session, cert_id: str) -> list:
    from app.models import EContractAttachment
    rows = (
        db.query(EContractAttachment)
        .filter(EContractAttachment.cert_id == cert_id)
        .order_by(EContractAttachment.created_at.asc())
        .all()
    )
    return [attachment_to_dict(a) for a in rows]


def attachment_file(db: Session, cert_id: str, att_id: int):
    """คืน (path, ชื่อไฟล์, mime) หรือ raise ถ้าไม่ได้เก็บตัวไฟล์ไว้"""
    from app.models import EContractAttachment
    a = (
        db.query(EContractAttachment)
        .filter(EContractAttachment.id == att_id, EContractAttachment.cert_id == cert_id)
        .first()
    )
    if not a:
        raise ValueError("ไม่พบไฟล์แนบ")
    if not a.stored or not a.storage_path:
        raise ValueError(
            "ไฟล์นี้บันทึกไว้เฉพาะลายนิ้วมือ ไม่ได้เก็บตัวไฟล์ "
            "(โหมดเก็บไฟล์ปิดอยู่ขณะอัปโหลด)"
        )
    full = os.path.join(ATTACHMENT_ROOT, a.storage_path)
    if not os.path.isfile(full):
        raise ValueError("ไฟล์หายจากที่จัดเก็บ — ตรวจสอบการสำรองข้อมูล")
    return full, a.filename, (a.content_type or "application/octet-stream")


# ── e-Original + e-Retention — ภาพรวมทั้งระบบ ────────────────────────────

def thai_day_start(days_back: int = 0) -> datetime:
    """เที่ยงคืนของวันตามเวลาไทย แปลงกลับเป็น UTC แบบ naive ให้ตรงกับที่เก็บใน DB"""
    now_th = datetime.now(timezone.utc) + timedelta(hours=7)
    start_th = now_th.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
    return (start_th - timedelta(hours=7)).replace(tzinfo=None)


def _scope_filter(q, scope: str):
    """จำกัดช่วงเวลา — ค่าเริ่มต้นเป็นวันนี้ เพราะการประเมิน 7 ขั้นตอนทำต่อใบรับรอง
    การดึงทั้งหมดจึงแพงขึ้นตามจำนวนสัญญาสะสม"""
    if scope == "all":
        return q
    days = {"today": 0, "7d": 6, "30d": 29}.get(scope, 0)
    return q.filter(EContractCert.created_at >= thai_day_start(days))


def originals_overview(db: Session, limit: int = 200, scope: str = "today",
                       q: str = "") -> dict:
    """สถานะความเป็นต้นฉบับ (ม.10) และการเก็บรักษา (ม.12)

    ดึงจากรายงาน 7 ขั้นตอนของแต่ละใบ เพื่อให้ตัวเลขตรงกับหน้ารายละเอียดเสมอ
    """
    from app.services import compliance_service

    query = _scope_filter(db.query(EContractCert), scope)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            (EContractCert.cert_id.like(like)) | (EContractCert.filename.like(like))
        )
    total_all = db.query(EContractCert).count()
    rows = query.order_by(EContractCert.created_at.desc()).limit(limit).all()
    out, locked, at_risk = [], 0, 0
    for cert in rows:
        try:
            rep = compliance_service.evaluate(db, cert)
        except Exception:
            continue
        orig = next((s for s in rep["steps"] if s["step"] == "e_original"), {})
        ret = next((s for s in rep["steps"] if s["step"] == "e_retention"), {})
        od, rd = orig.get("detail", {}), ret.get("detail", {})
        if orig.get("status") == "done":
            locked += 1
        if ret.get("status") in ("partial", "pending"):
            at_risk += 1
        out.append({
            "cert_id": cert.cert_id,
            "filename": cert.filename,
            "doc_format": cert.doc_format or "",
            "profile_key": cert.profile_key or "generic",
            "profile_name_th": rep["profile"].get("name_th", ""),
            "sha256": cert.sha256,
            "system_signature": cert.signature,
            "ntp_time": cert.ntp_time.isoformat() if cert.ntp_time else None,
            "ntp_server_name": cert.ntp_server_name,
            "signature_count": len(rep_signatures(rep)),
            "original": {
                "status": orig.get("status"),
                "summary_th": orig.get("summary_th", ""),
                "lock_on": od.get("lock_on", ""),
                "timestamp_kind": od.get("timestamp_kind", ""),
            },
            "retention": {
                "status": ret.get("status"),
                "summary_th": ret.get("summary_th", ""),
                "period_years": rd.get("period_years"),
                "keep_until": rd.get("keep_until"),
                "must_store": rd.get("must_store", []),
                "stored": rd.get("stored", {}),
                "missing": rd.get("missing", []),
                "audit_entries": rd.get("audit_entries", 0),
            },
        })
    return {
        "scope": scope,
        "query": (q or "").strip(),
        "total_all": total_all,
        "storage_mode": "hash_only",
        "storage_note_th": (
            "โหมดปัจจุบันเก็บเฉพาะลายนิ้วมือ (SHA-256) เวลา และหลักฐานประกอบ "
            "— ตัวไฟล์ไม่ถูกส่งออกจากเครื่องผู้ใช้และไม่ถูกเก็บในระบบ "
            "จึงยังไม่ครบเงื่อนไข 'เก็บรักษาตัวเอกสาร' ตาม ม.12"
        ),
        "total": len(out),
        "locked_originals": locked,
        "retention_incomplete": at_risk,
        "items": out,
    }


def rep_signatures(rep: dict) -> list:
    sig = next((s for s in rep["steps"] if s["step"] == "e_signature"), {})
    return (sig.get("detail") or {}).get("signers", [])


# ── Evidence bundle (Phase 3) ────────────────────────────────────────────

def build_evidence_bundle(db: Session, cert_id: str) -> bytes:
    """Build a tamper-evident .zip: certificate + signatures + audit trail +
    manifest (SHA-256 of each file). Self-contained legal evidence bundle for
    an electronic transaction. Returns the zip bytes, or raises ValueError."""
    from app.models import AuditLog  # local to avoid a top-level cycle
    d = detail(db, cert_id)
    if not d:
        raise ValueError("ไม่พบใบรับรอง")

    audits = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "econtract", AuditLog.resource_id == cert_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    audit_rows = [{
        "time": a.created_at.isoformat() if a.created_at else None,
        "action": a.action, "user": a.username, "ip": a.ip_address,
        "ntp_server": a.ntp_server, "details": a.details,
    } for a in audits]

    generated = datetime.now(timezone.utc).isoformat()

    compliance = d.pop("compliance", None)

    files: dict[str, bytes] = {}
    files["certificate.json"] = json.dumps(d, ensure_ascii=False, indent=2).encode()
    files["signatures.json"] = json.dumps(d.get("signatures", []), ensure_ascii=False, indent=2).encode()
    files["audit_trail.json"] = json.dumps(audit_rows, ensure_ascii=False, indent=2).encode()
    if compliance:
        # รายงาน 7 เรื่อง + โปรไฟล์ที่แช่แข็งไว้ — ผู้ตรวจสอบในอนาคตพิสูจน์ได้ว่า
        # ตอนทำสัญญา ระบบยึดกฎชุดไหน (ม.11 การชั่งน้ำหนักพยานหลักฐาน)
        files["compliance_7steps.json"] = json.dumps(compliance, ensure_ascii=False, indent=2).encode()
        # โซ่หลักฐาน — พิสูจน์ลำดับเหตุการณ์ ไม่ใช่แค่เนื้อหา (ม.11)
        from app.services import chain_service as _ch
        files["evidence_chain.json"] = json.dumps(
            _ch.chain(db, cert_id), ensure_ascii=False, indent=2).encode()
        row = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
        if row and row.effective_profile_json:
            files["contract_profile.json"] = row.effective_profile_json.encode()
        # แนบใบข้อมูลยื่นอากรแสตมป์เมื่อสัญญาชนิดนี้เข้าข่ายต้องเสีย
        sd = next((s for s in compliance["steps"] if s["step"] == "e_stamp_duty"), None)
        if row is not None and sd and sd.get("required"):
            from app.services import compliance_service as _cs
            payload = _cs.stamp_duty_payload(db, row)
            files["stamp_duty_as9.txt"] = _cs.stamp_duty_worksheet_text(payload).encode("utf-8")
    files["README.txt"] = (
        "ชุดหลักฐานธุรกรรมทางอิเล็กทรอนิกส์ (iVS e-Contract Evidence Bundle)\n"
        f"Cert ID     : {d['cert_id']}\n"
        f"เอกสาร       : {d['filename']}\n"
        f"ลายนิ้วมือ    : SHA-256 {d['sha256']}\n"
        f"เวลารับรอง   : {d['ntp_time']}  ({d['ntp_server_name']})\n"
        f"ลายเซ็นระบบ  : {d['signature']}\n"
        f"ผู้ลงนาม     : {len(d.get('signatures', []))} ราย\n"
        + (
            f"ประเภทสัญญา  : {compliance['profile'].get('name_th')} "
            f"(โปรไฟล์ {compliance['profile'].get('key')} v{compliance['profile'].get('version')})\n"
            f"ความครบถ้วน  : {compliance['summary']['required_done']}/"
            f"{compliance['summary']['required_total']} ขั้นตอนที่บังคับ\n"
            if compliance else ""
        )
        + f"สร้างบันเดิล : {generated}\n\n"
        "การตรวจสอบ:\n"
        "- เทียบ SHA-256 ของเอกสารต้นฉบับกับค่าใน certificate.json\n"
        "- ตรวจใบรับรอง/ลายเซ็นได้ที่เมนู e-Contract ของ iVS (ใช้ Cert ID หรือไฟล์เดิม)\n"
        "- compliance_7steps.json สรุปว่าเอกสารนี้ทำครบ 7 เรื่องของวงจร e-Contract หรือยัง\n"
        "- contract_profile.json คือกฎที่ใช้ประเมิน ณ วันที่ออกใบรับรอง (แช่แข็งไว้)\n"
        "- manifest.json ระบุ SHA-256 ของทุกไฟล์ในชุดนี้ (ตรวจความครบถ้วน)\n\n"
        "อ้างอิง: พ.ร.บ. ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ (integrity §12, ลายมือชื่อ §9/§26)\n"
    ).encode("utf-8")

    manifest = {
        "bundle": "iVS e-Contract Evidence Bundle",
        "cert_id": d["cert_id"],
        "generated_at": generated,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
