"""Data mart — outside data, fetched once and shared, with its provenance.

Before this, an app that needed data from elsewhere connected to it directly.
That means the key lives in that app, another app needing the same data gets
its own copy of the key, and nobody can answer "what outside data is flowing
into this installation" without reading every app.

Here the key stays in the Vault, the fetch happens once, and every record
carries where it came from and when it stops being kept.

Outside data is the highest-risk thing in the platform, because nobody here
controls what the other end sends. So every fetch is scanned for personal data
rather than trusting the source to send only what was agreed — and what the
scan finds is recorded on the source, where whoever configured it can see it.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models import DataMartRecord, DataMartSource, VaultKey
from app.services.pdpa_service import PII_PATTERNS
from app.services.vault_service import vault_service

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 30
MAX_PAYLOAD_CHARS = 2_000_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def scan_payload_for_pii(text: str) -> List[str]:
    """Which categories of personal data appear in what arrived.

    Reuses the same patterns the app scanner uses, so "PII" means one thing
    across iVS rather than one thing per feature.
    """
    import re
    found = []
    sample = text[:200_000]
    for category, patterns in PII_PATTERNS.items():
        for pat in patterns:
            try:
                if re.search(pat, sample, re.IGNORECASE):
                    found.append(category)
                    break
            except re.error:
                continue
    return found


async def fetch_once(db: Session, source: DataMartSource) -> Tuple[bool, str]:
    """Fetch this source now and store the result.

    Returns (ok, message). Failures are recorded on the source rather than
    raised, because a source that has been failing for a week is something the
    operator needs to see on the screen, not something buried in a log.
    """
    headers = {"Accept": "application/json"}
    if source.vault_key_name:
        key = db.query(VaultKey).filter(VaultKey.name == source.vault_key_name).first()
        if not key:
            msg = f"ไม่พบกุญแจชื่อ {source.vault_key_name} ใน Vault"
            _record_failure(db, source, msg)
            return False, msg
        try:
            secret = vault_service.decrypt(key.encrypted_value)
        except Exception:
            msg = "ถอดรหัสกุญแจจาก Vault ไม่สำเร็จ"
            _record_failure(db, source, msg)
            return False, msg
        header = source.auth_header or "Authorization"
        headers[header] = secret if header.lower() != "authorization" else f"Bearer {secret}"

    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            r = await client.request(source.method or "GET", source.url, headers=headers)
    except Exception as e:
        msg = f"เรียกแหล่งข้อมูลไม่สำเร็จ: {str(e)[:150]}"
        _record_failure(db, source, msg)
        return False, msg

    if r.status_code >= 400:
        msg = f"แหล่งข้อมูลตอบ HTTP {r.status_code}"
        _record_failure(db, source, msg)
        return False, msg

    text = r.text[:MAX_PAYLOAD_CHARS]
    pii = scan_payload_for_pii(text)

    expires = None
    if source.retention_days and source.retention_days > 0:
        expires = _now() + timedelta(days=source.retention_days)

    db.add(DataMartRecord(
        source_id=source.id,
        payload=text,
        content_hash=hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest(),
        fetched_at=_now(),
        expires_at=expires,
    ))
    source.last_fetch_at = _now()
    source.last_status = "ok"
    source.last_message = f"ได้ข้อมูล {len(text)} ตัวอักษร"
    source.last_pii_found = json.dumps(pii, ensure_ascii=False)
    db.commit()

    if pii:
        # Worth saying out loud: personal data arriving from outside is exactly
        # what needs a lawful basis and a retention decision behind it.
        logger.warning(
            f"Data mart '{source.name}': พบข้อมูลส่วนบุคคล {', '.join(pii)} "
            f"— ต้องมีฐานการประมวลผลรองรับ"
        )
    return True, "ok"


def _record_failure(db: Session, source: DataMartSource, message: str):
    source.last_fetch_at = _now()
    source.last_status = "failed"
    source.last_message = message[:2000]
    db.commit()
    logger.warning(f"Data mart '{source.name}' failed: {message}")


def latest(db: Session, source_id: int) -> Optional[dict]:
    """The most recent record for a source, parsed when it is JSON."""
    row = (
        db.query(DataMartRecord)
        .filter(DataMartRecord.source_id == source_id)
        .order_by(DataMartRecord.fetched_at.desc())
        .first()
    )
    if not row:
        return None
    try:
        data = json.loads(row.payload) if row.payload else None
    except Exception:
        data = row.payload
    return {
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "content_hash": row.content_hash,
        "data": data,
    }


def due_sources(db: Session) -> List[DataMartSource]:
    """Sources whose fetch interval has elapsed."""
    out = []
    now = _now()
    for s in db.query(DataMartSource).filter(DataMartSource.is_active == True).all():  # noqa: E712
        last = _aware(s.last_fetch_at)
        if last is None:
            out.append(s)
            continue
        if (now - last) >= timedelta(minutes=max(1, s.fetch_interval_minutes or 60)):
            out.append(s)
    return out


def purge_expired(db: Session) -> int:
    """Delete records past their retention date.

    Retention on outside data is not optional housekeeping: keeping personal
    data longer than the purpose requires is the violation, whether or not
    anyone ever looks at it again.
    """
    now = _now()
    n = (
        db.query(DataMartRecord)
        .filter(DataMartRecord.expires_at.isnot(None), DataMartRecord.expires_at <= now)
        .delete(synchronize_session=False)
    )
    if n:
        db.commit()
        logger.info(f"Data mart: purged {n} expired record(s)")
    return n


def to_dict(db: Session, s: DataMartSource) -> dict:
    try:
        pii = json.loads(s.last_pii_found or "[]")
    except Exception:
        pii = []
    count = db.query(DataMartRecord).filter(DataMartRecord.source_id == s.id).count()
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "url": s.url,
        "method": s.method or "GET",
        "vault_key_name": s.vault_key_name or "",
        "fetch_interval_minutes": s.fetch_interval_minutes,
        "retention_days": s.retention_days,
        "is_active": bool(s.is_active),
        "last_fetch_at": s.last_fetch_at.isoformat() if s.last_fetch_at else None,
        "last_status": s.last_status,
        "last_message": s.last_message or "",
        "pii_found": pii,
        "record_count": count,
    }
