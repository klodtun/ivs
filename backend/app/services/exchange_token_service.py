"""Issuing and checking the credentials that let one system call another.

This is the Vault's second job. Holding secrets was enough while apps were
islands; once they call each other, the question is no longer "where is the
key" but "who may call what, for how long, and can we take it back".

Four things this deliberately does:

* **Stores only a hash.** The plaintext appears once, at issue. A dump of this
  table is not a set of working credentials.
* **Separates read from write.** They are different tokens, never one with both
  powers, so handing a model read access does not hand it the ability to cancel
  a booking.
* **Refuses an open-ended write token.** A permanent read feed between two
  systems is a normal arrangement; a permanent write credential is the one most
  likely to outlive the reason it was created.
* **Caps calls per hour.** AI callers retry, and loops happen. Without a ceiling
  a single bad prompt can exhaust an app — or a paid model budget — in minutes.
"""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models import App, ExchangeToken, TokenScope

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32
PREFIX_LEN = 8

# Methods that change state. Anything here needs a write token; everything else
# is satisfied by a read token.
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Ceiling on how long a write token may live. Long enough for an event, short
# enough that a forgotten one stops working.
MAX_WRITE_TTL_HOURS = 24 * 30


def _hash(token: str) -> str:
    """Keyed hash, so the stored value is useless without this install's key."""
    return hmac.new(
        settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; compare them as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── issuing ──────────────────────────────────────────────────────────

def issue(
    db: Session,
    target_app_id: int,
    caller_name: str,
    scope: TokenScope,
    caller_kind: str = "app",
    allowed_paths: Optional[List[str]] = None,
    ttl_hours: Optional[int] = None,
    rate_limit_per_hour: int = 1000,
    label: str = "",
    created_by: Optional[int] = None,
) -> Tuple[ExchangeToken, str]:
    """Create a token. Returns (row, plaintext) — the plaintext is not recoverable.

    Raises ValueError when asked for a write token with no expiry.
    """
    if scope == TokenScope.WRITE:
        if ttl_hours is None:
            raise ValueError(
                "โทเคนสำหรับเขียนข้อมูลต้องกำหนดอายุเสมอ — "
                "โทเคนเขียนที่ไม่มีวันหมดอายุคือสิ่งที่ถูกลืมแล้วถูกใช้ในทางที่ผิดได้ง่ายที่สุด"
            )
        if ttl_hours > MAX_WRITE_TTL_HOURS:
            raise ValueError(f"อายุโทเคนสำหรับเขียนต้องไม่เกิน {MAX_WRITE_TTL_HOURS} ชั่วโมง")

    plaintext = f"ivs_{scope.value}_{secrets.token_urlsafe(TOKEN_BYTES)}"
    row = ExchangeToken(
        token_hash=_hash(plaintext),
        token_prefix=plaintext[:PREFIX_LEN],
        label=label[:200],
        caller_kind=caller_kind if caller_kind in ("app", "ai", "external") else "external",
        caller_name=caller_name[:200],
        target_app_id=target_app_id,
        scope=scope,
        allowed_paths=json.dumps(allowed_paths or ["*"], ensure_ascii=False),
        expires_at=(_now() + timedelta(hours=ttl_hours)) if ttl_hours else None,
        rate_limit_per_hour=max(1, int(rate_limit_per_hour)),
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        f"exchange token issued: {row.token_prefix}… {caller_name} -> app {target_app_id} "
        f"({scope.value}, expires {row.expires_at or 'never'})"
    )
    return row, plaintext


def revoke(db: Session, token_id: int) -> Optional[ExchangeToken]:
    row = db.query(ExchangeToken).filter(ExchangeToken.id == token_id).first()
    if not row or row.revoked_at:
        return row
    row.revoked_at = _now()
    db.commit()
    db.refresh(row)
    return row


# ── checking ─────────────────────────────────────────────────────────

def _path_allowed(row: ExchangeToken, method: str, path: str) -> bool:
    try:
        allowed = json.loads(row.allowed_paths or '["*"]')
    except Exception:
        allowed = ["*"]
    if "*" in allowed:
        return True
    method = method.upper()
    for entry in allowed:
        entry = (entry or "").strip()
        if not entry:
            continue
        if " " in entry:
            m, _, p = entry.partition(" ")
            if m.upper() not in (method, "*"):
                continue
            p = p.strip()
        else:
            p = entry
        # A trailing * matches a prefix, so "/bookings/*" covers the collection.
        if p.endswith("*"):
            if path.startswith(p[:-1]):
                return True
        elif path == p:
            return True
    return False


def _consume_rate(db: Session, row: ExchangeToken) -> bool:
    """Count this call against the hourly cap. False when the cap is reached."""
    now = _now()
    start = _aware(row.window_start)
    if start is None or (now - start) >= timedelta(hours=1):
        row.window_start = now
        row.window_count = 1
        return True
    if (row.window_count or 0) >= row.rate_limit_per_hour:
        return False
    row.window_count = (row.window_count or 0) + 1
    return True


def verify(
    db: Session, token: str, method: str, path: str
) -> Tuple[Optional[ExchangeToken], str]:
    """Check a token for one specific call.

    Returns (row, "") when the call is allowed, or (None, reason) — the reason
    is written to the audit log and returned to the caller, because a refusal
    nobody can explain is a refusal that gets worked around.
    """
    if not token:
        return None, "ไม่ได้ส่งโทเคน"

    row = db.query(ExchangeToken).filter(
        ExchangeToken.token_hash == _hash(token)
    ).first()
    if not row:
        return None, "โทเคนไม่ถูกต้อง"
    if row.revoked_at:
        return None, "โทเคนถูกเพิกถอนแล้ว"

    expires = _aware(row.expires_at)
    if expires and expires <= _now():
        return None, "โทเคนหมดอายุแล้ว"

    method_upper = (method or "GET").upper()
    if method_upper in WRITE_METHODS and row.scope != TokenScope.WRITE:
        return None, "โทเคนนี้อ่านได้อย่างเดียว ใช้เขียนข้อมูลไม่ได้"

    if not _path_allowed(row, method_upper, path):
        return None, f"โทเคนนี้ไม่ได้รับอนุญาตให้เรียก {method_upper} {path}"

    if not _consume_rate(db, row):
        return None, f"เกินเพดานการเรียก {row.rate_limit_per_hour} ครั้งต่อชั่วโมง"

    row.use_count = (row.use_count or 0) + 1
    row.last_used_at = _now()
    db.commit()
    return row, ""


# ── listing ──────────────────────────────────────────────────────────

def to_dict(row: ExchangeToken, app_name: str = "") -> dict:
    expires = _aware(row.expires_at)
    now = _now()
    if row.revoked_at:
        state = "revoked"
    elif expires and expires <= now:
        state = "expired"
    else:
        state = "active"
    try:
        paths = json.loads(row.allowed_paths or '["*"]')
    except Exception:
        paths = ["*"]
    return {
        "id": row.id,
        "prefix": row.token_prefix,
        "label": row.label or "",
        "caller_kind": row.caller_kind,
        "caller_name": row.caller_name,
        "target_app_id": row.target_app_id,
        "target_app_name": app_name,
        "scope": row.scope.value if hasattr(row.scope, "value") else str(row.scope),
        "allowed_paths": paths,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "rate_limit_per_hour": row.rate_limit_per_hour,
        "use_count": row.use_count or 0,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "state": state,
    }


def list_for_app(db: Session, app_id: int) -> List[dict]:
    app = db.query(App).filter(App.id == app_id).first()
    rows = (
        db.query(ExchangeToken)
        .filter(ExchangeToken.target_app_id == app_id)
        .order_by(ExchangeToken.created_at.desc())
        .all()
    )
    return [to_dict(r, app.name if app else "") for r in rows]
