"""Centralised data retention for IVS.

Reference: พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560
- §26 requires service providers to keep computer-traffic data for at
  least 90 days, with a competent officer empowered to extend the
  requirement up to 2 years (730 days) or more in specific cases.

This module is the single source of truth for "how long do we keep X".
Retention values live in the `system_config` table under keys
`retention.<log_type>` so an admin can change them at runtime without
restarting the service. A daily background loop in main.py calls
`purge_all()` to enforce the policy on every log table the project owns.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models import (
    SystemConfig,
    AuditLog,
    AppLogEntry,
    ResourceMetric,
    AuditLogExport,
)
from app.config import settings

logger = logging.getLogger(__name__)


# Defaults applied when no SystemConfig row exists yet.
DEFAULT_RETENTION_DAYS: Dict[str, int] = {
    "audit_logs": 730,       # 2 years — standard for compliance evidence
    "app_logs": 90,          # the §26 minimum
    "resource_metrics": 30,  # short-lived, just for charts
    "exports": 365,          # exported audit bundles
}

# Inclusive bounds the admin form should clamp to. Note we deliberately
# allow values above 730 because §26 says the officer can require longer
# — we keep the door open up to 10 years, with a UI note when above 730.
MIN_DAYS_BY_TYPE: Dict[str, int] = {
    "audit_logs": 90,
    "app_logs": 90,
    "resource_metrics": 7,
    "exports": 30,
}
MAX_RECOMMENDED = 730  # 2 years
MAX_ALLOWED = 3650     # 10 years — hard cap so a typo can't pin forever


def _config_key(log_type: str) -> str:
    return f"retention.{log_type}"


def get_retention_days(db: Session, log_type: str) -> int:
    """Resolve the configured retention (days) for a log type. Falls back to
    the hard-coded default if the row doesn't exist or is unparsable."""
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == _config_key(log_type))
        .first()
    )
    if row and row.value and row.value.isdigit():
        return int(row.value)
    return DEFAULT_RETENTION_DAYS.get(log_type, MAX_RECOMMENDED)


def set_retention_days(db: Session, log_type: str, days: int) -> int:
    """Persist a retention value, clamped to [MIN_DAYS_BY_TYPE, MAX_ALLOWED]."""
    if log_type not in DEFAULT_RETENTION_DAYS:
        raise ValueError(f"Unknown log type: {log_type}")
    min_days = MIN_DAYS_BY_TYPE.get(log_type, 90)
    clamped = max(min_days, min(days, MAX_ALLOWED))
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == _config_key(log_type))
        .first()
    )
    if row:
        row.value = str(clamped)
    else:
        db.add(SystemConfig(key=_config_key(log_type), value=str(clamped)))
    db.commit()
    return clamped


def get_all_settings(db: Session) -> Dict[str, Dict[str, int]]:
    """Snapshot all retention values for the API/UI."""
    return {
        log_type: {
            "days": get_retention_days(db, log_type),
            "default": DEFAULT_RETENTION_DAYS[log_type],
            "min": MIN_DAYS_BY_TYPE[log_type],
            "max_recommended": MAX_RECOMMENDED,
            "max_allowed": MAX_ALLOWED,
        }
        for log_type in DEFAULT_RETENTION_DAYS
    }


def purge_all(db: Session) -> Dict[str, int]:
    """Apply each log type's retention policy. Returns rows deleted per type."""
    now = datetime.now(timezone.utc)
    result: Dict[str, int] = {}

    # ── Audit logs (system events) ──
    days = get_retention_days(db, "audit_logs")
    cutoff = now - timedelta(days=days)
    n = (
        db.query(AuditLog)
        .filter(AuditLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    result["audit_logs"] = n

    # ── App container logs ──
    days = get_retention_days(db, "app_logs")
    cutoff = now - timedelta(days=days)
    n = (
        db.query(AppLogEntry)
        .filter(AppLogEntry.timestamp < cutoff)
        .delete(synchronize_session=False)
    )
    result["app_logs"] = n

    # ── Resource metrics ──
    days = get_retention_days(db, "resource_metrics")
    cutoff = now - timedelta(days=days)
    n = (
        db.query(ResourceMetric)
        .filter(ResourceMetric.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    result["resource_metrics"] = n

    # ── Audit-export bundles (DB row + the .zip/.md file on disk) ──
    days = get_retention_days(db, "exports")
    cutoff = now - timedelta(days=days)
    expired = db.query(AuditLogExport).filter(AuditLogExport.created_at < cutoff).all()
    exports_dir = os.path.join(
        os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")),
        "exports",
    )
    removed_files = 0
    for row in expired:
        path = os.path.join(exports_dir, row.filename)
        if os.path.exists(path):
            try:
                os.remove(path)
                removed_files += 1
            except OSError as e:
                logger.warning(f"Could not delete export file {path}: {e}")
        db.delete(row)
    result["exports"] = len(expired)
    result["exports_files_removed"] = removed_files

    db.commit()

    # Only log when we actually deleted something — avoids noisy daily logs
    nonzero = {k: v for k, v in result.items() if v}
    if nonzero:
        logger.info(f"Retention purge: {nonzero}")
    return result
