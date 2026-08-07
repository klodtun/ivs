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
from datetime import datetime, timezone

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
        "method": s.method,
        "identity_ref": s.identity_ref,
        "signed_at": s.signed_at.isoformat() if s.signed_at else None,
        "ip_address": s.ip_address,
        "signature": s.signature,
    }


def add_signature(db: Session, cert_id: str, signer_name: str, method: str = "typed",
                  identity_ref: str = "", ip: str = "", created_by: int = None) -> dict:
    """Record an electronic signature on a certificate (§9/§26)."""
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")
    now = ntp_service.now()
    row = EContractSignature(
        cert_id=cert_id, signer_name=signer_name[:200],
        method=method if method in ("typed", "drawn", "otp") else "typed",
        identity_ref=(identity_ref or "")[:300000], signed_at=now,  # allow a drawn-signature PNG data URI
        ip_address=(ip or "")[:45], signature="", created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.signature = _sign_signature(cert.sha256, row.signer_name, row.signed_at.isoformat(), row.method)
    db.commit()
    db.refresh(row)
    return sig_to_dict(row)


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
