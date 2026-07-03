"""
Password Policy — Policy-as-Code for user credentials.

The policy is set in the PDPA menu (system_config keys `policy.password.*`)
and enforced wherever a password is set, and surfaced as a warning on the
user-management screen. Keeping it in system_config means an admin can
tighten it at runtime without a code change, and it travels with the DB.
"""
import logging
from typing import Dict, List

from sqlalchemy.orm import Session
from app.models import SystemConfig

logger = logging.getLogger(__name__)

# key -> (default, kind) ; kind "int" or "bool"
_DEFAULTS = {
    "policy.password.min_length": ("8", "int"),
    "policy.password.require_upper": ("true", "bool"),
    "policy.password.require_lower": ("true", "bool"),
    "policy.password.require_number": ("true", "bool"),
    "policy.password.require_symbol": ("false", "bool"),
}

MIN_ALLOWED_LENGTH = 6   # hard floor so the policy can't be set uselessly low
MAX_ALLOWED_LENGTH = 128


def _get(db: Session, key: str) -> str:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row and row.value:
        return row.value
    return _DEFAULTS[key][0]


def get_policy(db: Session) -> Dict:
    """Return the effective password policy as typed values."""
    def as_bool(v: str) -> bool:
        return str(v).lower() == "true"
    ml = _get(db, "policy.password.min_length")
    try:
        min_length = max(MIN_ALLOWED_LENGTH, min(int(ml), MAX_ALLOWED_LENGTH))
    except ValueError:
        min_length = 8
    return {
        "min_length": min_length,
        "require_upper": as_bool(_get(db, "policy.password.require_upper")),
        "require_lower": as_bool(_get(db, "policy.password.require_lower")),
        "require_number": as_bool(_get(db, "policy.password.require_number")),
        "require_symbol": as_bool(_get(db, "policy.password.require_symbol")),
    }


def set_policy(db: Session, policy: Dict) -> Dict:
    """Persist policy fields. Only known keys are written; length clamped."""
    def _upsert(key: str, value: str):
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))

    if "min_length" in policy and policy["min_length"] is not None:
        ml = max(MIN_ALLOWED_LENGTH, min(int(policy["min_length"]), MAX_ALLOWED_LENGTH))
        _upsert("policy.password.min_length", str(ml))
    for flag in ("require_upper", "require_lower", "require_number", "require_symbol"):
        if flag in policy and policy[flag] is not None:
            _upsert(f"policy.password.{flag}", "true" if policy[flag] else "false")
    db.commit()
    return get_policy(db)


def validate_password(password: str, db: Session) -> List[str]:
    """Return a list of unmet-requirement keys (empty = valid). Keys map to
    i18n messages on the frontend: length, upper, lower, number, symbol."""
    p = get_policy(db)
    fails: List[str] = []
    if len(password or "") < p["min_length"]:
        fails.append("length")
    if p["require_upper"] and not any(c.isupper() for c in password):
        fails.append("upper")
    if p["require_lower"] and not any(c.islower() for c in password):
        fails.append("lower")
    if p["require_number"] and not any(c.isdigit() for c in password):
        fails.append("number")
    if p["require_symbol"] and not any(not c.isalnum() for c in password):
        fails.append("symbol")
    return fails
