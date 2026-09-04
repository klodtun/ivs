"""Field-level PDPA policy — the PII scan turned into a rule that is enforced.

The scan in pdpa_service already finds which fields hold personal data, but its
output only landed in `app_pdpa.pii_auto_detected`, where nothing acted on it.
That is fine while apps are islands. The moment apps exchange data and AI can
call their APIs, "we scanned it" stops being an answer — the finding has to
become a rule that runs on every response.

That is what this module is: derive a draft rule per field from the scan, let a
human confirm it, then apply it to any payload leaving the app.

Two decisions worth keeping:

* **Defaults are restrictive, and unconfirmed rules still apply.** A fresh scan
  can only ever narrow access, never widen it. If a scan discovers a new field
  the day before the festival, that field is masked from the moment it is seen,
  not from the moment someone gets round to reviewing it.
* **Masking uses the existing HMAC anonymizer**, so the same email becomes the
  same token every time. Operations can still correlate "this person again"
  across apps without anyone learning who it is.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import AppFieldPolicy, FieldAction
from app.services.pii_anonymizer import _tok

logger = logging.getLogger(__name__)

# What a newly discovered field gets before anyone reviews it. Identity
# documents and credentials are never masked-and-sent — a masked national ID is
# still a national ID's shape, and there is no legitimate reason for one to
# cross an app boundary at all.
DEFAULT_ACTION_BY_CATEGORY: Dict[str, FieldAction] = {
    "บัตรประชาชน/Passport": FieldAction.BLOCK,
    "Username/Password": FieldAction.BLOCK,
    "Cookie/Session": FieldAction.BLOCK,
    "อีเมล": FieldAction.MASK,
    "เบอร์โทรศัพท์": FieldAction.MASK,
    "ชื่อ-นามสกุล": FieldAction.MASK,
    "ที่อยู่": FieldAction.MASK,
    "วันเกิด/อายุ": FieldAction.MASK,
    "LINE ID": FieldAction.MASK,
    "IP Address": FieldAction.MASK,
}

# Anything the scan flags that isn't in the table above.
FALLBACK_ACTION = FieldAction.MASK

# Field names are compared case-insensitively and without separators, so a
# policy written for "email" also covers "Email", "e_mail" and "e-mail".
def normalize(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def default_action_for(category: str) -> FieldAction:
    return DEFAULT_ACTION_BY_CATEGORY.get(category, FALLBACK_ACTION)


# ── deriving rules from a scan ───────────────────────────────────────

def derive_from_scan(db: Session, app_id: int, scan_result: dict) -> dict:
    """Create draft rules for fields the scan found that have no rule yet.

    Existing rules are never overwritten: a confirmed decision outranks a later
    scan, otherwise re-scanning would silently undo someone's review.
    """
    details = scan_result.get("scan_details") or []
    existing = {
        normalize(p.field_name): p
        for p in db.query(AppFieldPolicy).filter(AppFieldPolicy.app_id == app_id).all()
    }

    created, skipped = [], 0
    seen_this_pass = set()
    for d in details:
        raw = (d.get("field") or "").strip()
        if not raw:
            continue
        key = normalize(raw)
        if not key or key in seen_this_pass:
            continue
        seen_this_pass.add(key)
        if key in existing:
            skipped += 1
            continue
        category = d.get("category") or ""
        row = AppFieldPolicy(
            app_id=app_id,
            field_name=raw,
            category=category,
            action=default_action_for(category),
            confirmed=False,
            origin="scan",
        )
        db.add(row)
        created.append({"field": raw, "category": category, "action": row.action.value})

    db.commit()
    return {
        "created": len(created),
        "kept": skipped,
        "fields": created,
        "pending_review": db.query(AppFieldPolicy)
            .filter(AppFieldPolicy.app_id == app_id, AppFieldPolicy.confirmed == False)  # noqa: E712
            .count(),
    }


# ── applying rules to outgoing data ──────────────────────────────────

def _policy_map(db: Session, app_id: int) -> Dict[str, FieldAction]:
    rows = db.query(AppFieldPolicy).filter(AppFieldPolicy.app_id == app_id).all()
    return {normalize(r.field_name): r.action for r in rows}


def _mask_value(value: Any) -> str:
    """Replace a value with a stable opaque token.

    Same input, same token, forever — keyed by SECRET_KEY like the rest of the
    anonymizer, so correlation survives without re-identification.
    """
    if value is None:
        return ""
    return _tok(str(value), prefix="")


def apply_policy(
    db: Session, app_id: int, payload: Any
) -> Tuple[Any, List[dict]]:
    """Return `payload` with this app's field rules applied, plus what changed.

    Walks dicts and lists to any depth, because real API responses nest — a
    booking list has a guest object inside each row, and a rule about `email`
    has to reach it there too.

    The second return value is the record of what was blocked or masked; the
    caller writes it to the audit log, so "what did this API actually disclose"
    has an answer after the fact.
    """
    policies = _policy_map(db, app_id)
    if not policies:
        return payload, []

    applied: List[dict] = []

    def walk(node: Any, path: str = "") -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                here = f"{path}.{k}" if path else k
                action = policies.get(normalize(k))
                if action == FieldAction.BLOCK:
                    applied.append({"field": here, "action": "block"})
                    continue
                if action == FieldAction.MASK and not isinstance(v, (dict, list)):
                    out[k] = _mask_value(v)
                    applied.append({"field": here, "action": "mask"})
                    continue
                out[k] = walk(v, here)
            return out
        if isinstance(node, list):
            return [walk(v, f"{path}[]") for v in node]
        return node

    return walk(payload), applied


# ── review ───────────────────────────────────────────────────────────

def confirm(
    db: Session, app_id: int, field_name: str, action: FieldAction,
    user_id: int, note: str = "",
) -> Optional[AppFieldPolicy]:
    """Record a human decision for one field. Creates the rule if it's new."""
    key = normalize(field_name)
    row = next(
        (p for p in db.query(AppFieldPolicy).filter(AppFieldPolicy.app_id == app_id).all()
         if normalize(p.field_name) == key),
        None,
    )
    if row is None:
        row = AppFieldPolicy(app_id=app_id, field_name=field_name, origin="manual")
        db.add(row)
    row.action = action
    row.confirmed = True
    row.confirmed_by = user_id
    row.confirmed_at = datetime.now(timezone.utc)
    if note:
        row.note = note[:2000]
    db.commit()
    db.refresh(row)
    return row


def summary(db: Session, app_id: int) -> dict:
    rows = db.query(AppFieldPolicy).filter(AppFieldPolicy.app_id == app_id).all()
    return {
        "total": len(rows),
        "pending_review": sum(1 for r in rows if not r.confirmed),
        "blocked": sum(1 for r in rows if r.action == FieldAction.BLOCK),
        "masked": sum(1 for r in rows if r.action == FieldAction.MASK),
        "allowed": sum(1 for r in rows if r.action == FieldAction.ALLOW),
        "fields": [
            {
                "id": r.id,
                "field_name": r.field_name,
                "category": r.category,
                "action": r.action.value,
                "confirmed": bool(r.confirmed),
                "origin": r.origin,
                "note": r.note or "",
            }
            for r in sorted(rows, key=lambda x: (x.confirmed, x.field_name))
        ],
    }
