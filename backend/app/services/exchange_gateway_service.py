"""The one road between apps — where the token, the policy and the log meet.

Everything the exchange layer promises happens here, in this order:

    token → idempotency → forward → field policy → audit

The order matters. Checking the token first means an unauthorised call never
reaches the app at all. Filtering after the app responds means the app does not
have to know anything about PDPA — it answers as it always has, and what leaves
iVS is what the app's own field rules allow. Logging last means the audit entry
records what was actually disclosed, not what was requested.

The app is reached on loopback. A protected app is already bound there by the
gate; a public one is reachable on its own port. Either way the call goes to
127.0.0.1, so this path is not a way around the login gate for anyone on the
network.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models import App, ExchangeToken, IdempotencyRecord, TokenScope
from app.services import field_policy_service as field_policy
from app.services.app_gate_service import internal_port

logger = logging.getLogger(__name__)

UPSTREAM_TIMEOUT_SECONDS = 30

# How long a remembered write result stays valid. Long enough to cover the
# retries of one working session, short enough that a key reused next week is
# treated as a new request.
IDEMPOTENCY_TTL = timedelta(hours=24)

# Headers that describe this connection rather than the request, and must not
# be passed to the app or returned to the caller.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def upstream_base(app: App) -> Optional[str]:
    """Where this app actually listens, from iVS's point of view."""
    if not app.port:
        return None
    port = internal_port(app.port) if app.access_mode == "protected" else app.port
    return f"http://127.0.0.1:{port}"


def _body_hash(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── idempotency ──────────────────────────────────────────────────────

def check_idempotency(
    db: Session, token: ExchangeToken, key: str, method: str, path: str, body: bytes
) -> Tuple[Optional[dict], Optional[str]]:
    """Look for a remembered result.

    Returns (replay, conflict). `replay` is the earlier response to return
    as-is; `conflict` is set when the same key arrives with different content,
    which is a caller bug and is worth saying out loud rather than answering
    with a result that does not match what was asked.
    """
    if not key:
        return None, None
    row = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.token_id == token.id, IdempotencyRecord.idem_key == key)
        .first()
    )
    if not row:
        return None, None

    created = _aware(row.created_at)
    if created and (_now() - created) > IDEMPOTENCY_TTL:
        db.delete(row)
        db.commit()
        return None, None

    if row.request_hash != _body_hash(body):
        return None, (
            "ใช้ Idempotency-Key ซ้ำกับคำขอที่เนื้อหาต่างกัน — "
            "คีย์เดียวกันต้องหมายถึงคำขอเดียวกันเท่านั้น"
        )

    try:
        payload = json.loads(row.response_body) if row.response_body else None
    except Exception:
        payload = None
    return {"status_code": row.status_code, "body": payload, "replayed": True}, None


def remember(
    db: Session, token: ExchangeToken, key: str, method: str, path: str,
    body: bytes, status_code: int, response: Any,
):
    if not key:
        return
    try:
        db.add(IdempotencyRecord(
            token_id=token.id,
            idem_key=key[:200],
            method=method,
            path=path[:500],
            request_hash=_body_hash(body),
            status_code=status_code,
            response_body=json.dumps(response, ensure_ascii=False)[:200000],
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"could not store idempotency record: {e}")


# ── forwarding ───────────────────────────────────────────────────────

async def forward(
    app: App, method: str, path: str, query: str,
    headers: Dict[str, str], body: bytes, caller: str,
) -> Tuple[int, Any, Dict[str, str], str, bytes]:
    """Call the app. Returns (status, parsed_body, headers, error, raw_body).

    Only JSON bodies are filtered — the field rules operate on fields, and a
    PDF or an image has none. Anything that isn't JSON is returned byte for
    byte, and the audit entry records that no filtering happened, so a caller
    fetching a file still gets the file.
    """
    base = upstream_base(app)
    if not base:
        return 503, None, {}, "แอปนี้ไม่มีพอร์ต จึงเรียกไม่ได้", b""

    fwd = {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}
    # Tell the app who is calling, the same way the login gate does. The app can
    # trust it because it cannot be set from outside — this is the only way in.
    fwd["X-IVS-Caller"] = caller
    fwd["X-IVS-Via"] = "exchange"

    url = f"{base}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
            r = await client.request(method, url, headers=fwd, content=body or None)
    except httpx.TimeoutException:
        return 504, None, {}, "แอปปลายทางไม่ตอบภายในเวลาที่กำหนด", b""
    except Exception as e:
        logger.warning(f"exchange forward failed for {app.slug}: {e}")
        return 502, None, {}, f"เรียกแอปปลายทางไม่สำเร็จ: {str(e)[:120]}", b""

    out_headers = {
        k: v for k, v in r.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "content-encoding"
    }
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            return r.status_code, r.json(), out_headers, "", r.content
        except Exception:
            # Claimed JSON but isn't. Pass it through rather than dropping it,
            # and let the audit entry say the rules could not run.
            return r.status_code, None, out_headers, "non-json", r.content
    return r.status_code, None, out_headers, "non-json", r.content


def apply_field_rules(db: Session, app_id: int, payload: Any) -> Tuple[Any, list]:
    """Run the app's field rules over what it returned.

    This is where opening an API stops meaning opening personal data: the app
    answers exactly as it always did, and the fields it is not allowed to
    disclose are removed or masked on the way out.
    """
    return field_policy.apply_policy(db, app_id, payload)


def summarise(applied: list) -> str:
    """One line for the audit entry: what was withheld, and how."""
    if not applied:
        return "ไม่มีฟิลด์ถูกกรอง"
    blocked = [a["field"] for a in applied if a["action"] == "block"]
    masked = [a["field"] for a in applied if a["action"] == "mask"]
    parts = []
    if blocked:
        parts.append(f"ตัดออก {len(blocked)} ฟิลด์ ({', '.join(blocked[:5])})")
    if masked:
        parts.append(f"ปิดบัง {len(masked)} ฟิลด์ ({', '.join(masked[:5])})")
    return " · ".join(parts)
