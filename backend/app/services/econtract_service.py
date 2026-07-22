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
import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EContractCert
from app.services.ntp_service import ntp_service


def _sign(sha256: str, ntp_iso: str) -> str:
    """HMAC-SHA256(sha256 | ntp_time) with the instance SECRET_KEY."""
    msg = f"{sha256}|{ntp_iso}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _cert_id() -> str:
    return "ECT-" + secrets.token_hex(8).upper()


def certify(db: Session, filename: str, data: bytes, signer: str = "",
            note: str = "", created_by: int = None) -> dict:
    """Issue an integrity + trusted-timestamp certificate for `data`."""
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
    }
