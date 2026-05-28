"""Persistent per-app log collection.

The user-facing AppCard "View Logs" button reads from `docker logs` live —
that's intentional, it's fast and shows the freshest tail. But Docker
containers retain at most a few MB of logs by default, so for COMPLIANCE
we mirror those lines into the database with 90-day retention as required
by พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560.

These rows are NOT shown in the audit-log UI (kept separate from
AuditLog). They surface only when an admin exports the audit bundle —
each app gets its own subfolder/file inside the .zip.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import App, AppStatus, AppLogEntry
from app.services.docker_service import docker_service
from app.services.pii_anonymizer import anonymize as anonymize_pii

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90
MAX_LINE_LENGTH = 8000  # truncate pathologically long lines (eg base64 dumps)

# In-memory checkpoint: app_id -> last timestamp we wrote for that app.
# Cheap state — on restart we rebuild it from the DB so we don't double-write.
_checkpoints: Dict[int, datetime] = {}


def _bootstrap_checkpoints(db: Session) -> None:
    """On startup, seed _checkpoints from the latest row per app in the DB
    so a restart doesn't re-insert lines we already have."""
    rows = (
        db.query(AppLogEntry.app_id, func.max(AppLogEntry.timestamp))
        .group_by(AppLogEntry.app_id)
        .all()
    )
    for app_id, latest in rows:
        if latest is not None:
            # SQLite stores naive datetimes; treat as UTC
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            _checkpoints[app_id] = latest
    logger.info(f"App-log collector: bootstrapped {len(_checkpoints)} checkpoint(s) from DB")


def _parse_docker_log_line(line: str) -> Optional[tuple[datetime, str]]:
    """Parse `2026-05-27T12:34:56.789012345Z <log>` → (datetime_utc, log)."""
    parts = line.split(" ", 1)
    if len(parts) < 2:
        return None
    ts_raw, text = parts[0], parts[1]
    # Docker uses nanosecond precision (9 fractional digits + Z); Python's
    # fromisoformat in 3.9 doesn't accept that — trim to microseconds.
    if not ts_raw.endswith("Z"):
        return None
    core = ts_raw[:-1]  # drop trailing Z
    if "." in core:
        head, frac = core.split(".", 1)
        frac = frac[:6]  # microseconds at most
        core = f"{head}.{frac}"
    try:
        dt = datetime.fromisoformat(core).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt, text


def collect_one_pass(db: Session) -> int:
    """Pull new log lines from every running container, persist them.

    Returns the number of new rows written.
    """
    if not docker_service._ensure_client():
        return 0

    inserted = 0
    apps = (
        db.query(App)
        .filter(App.status == AppStatus.RUNNING, App.container_id.isnot(None))
        .all()
    )
    for app in apps:
        # Source of truth for "since" is the latest row in the DB — that way
        # multiple processes (or a restarted process) never re-insert the same
        # line. In-memory checkpoint is just a fast-path cache.
        cached = _checkpoints.get(app.id)
        if cached is None:
            db_latest = (
                db.query(func.max(AppLogEntry.timestamp))
                .filter(AppLogEntry.app_id == app.id)
                .scalar()
            )
            if db_latest is not None:
                if db_latest.tzinfo is None:
                    db_latest = db_latest.replace(tzinfo=timezone.utc)
                cached = db_latest
        # Default lookback: 5 minutes (first time we ever see this app).
        # Avoids replaying hours of old logs when an app is freshly registered.
        since = cached or (datetime.now(timezone.utc) - timedelta(minutes=5))
        # Try container_id first (correct, fastest), then fall back to the
        # conventional name `ivs-<slug>`. The name lookup catches the case
        # where someone rebuilt the container outside IVS, leaving the DB
        # row with a stale ID.
        container = None
        for lookup in (app.container_id, f"ivs-{app.slug}"):
            if not lookup:
                continue
            try:
                container = docker_service.client.containers.get(lookup)
                break
            except Exception:
                continue
        if container is None:
            continue

        try:
            # `since` parameter accepts datetime — Docker SDK converts to epoch.
            raw = container.logs(timestamps=True, since=since).decode(
                "utf-8", errors="replace"
            )
        except Exception as e:
            logger.warning(f"App-log collector: get logs failed for {app.slug}: {e}")
            continue

        latest = since
        for line in raw.splitlines():
            parsed = _parse_docker_log_line(line)
            if parsed is None:
                continue
            ts, text = parsed
            # `since` is inclusive, so skip the exact-equal boundary line we
            # already stored in the previous pass.
            if ts <= since:
                continue
            # Level 0 → Level 1 boundary: scrub PII before persisting.
            # The raw line never touches the database in identifiable form.
            anonymized = anonymize_pii(text)
            db.add(
                AppLogEntry(
                    app_id=app.id,
                    timestamp=ts,
                    log_line=anonymized[:MAX_LINE_LENGTH],
                    stream="stdout",
                )
            )
            inserted += 1
            if ts > latest:
                latest = ts

        if latest > since:
            _checkpoints[app.id] = latest

    if inserted:
        db.commit()
    return inserted


def purge_old_logs(db: Session) -> int:
    """DEPRECATED — kept as a thin wrapper so older callers don't break.

    The single source of truth for retention is now
    `services.retention_service.purge_all()`, which reads the configured
    retention from SystemConfig (default 90 days, can be raised by an
    admin up to 10 years per §26 officer-order rules).
    """
    from app.services import retention_service
    result = retention_service.purge_all(db)
    return result.get("app_logs", 0)


def get_logs_for_export(
    db: Session,
    app_id: int,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> list:
    """Fetch persisted app logs in the given date range (ascending)."""
    q = db.query(AppLogEntry).filter(AppLogEntry.app_id == app_id)
    if start_date:
        q = q.filter(AppLogEntry.timestamp >= start_date)
    if end_date:
        q = q.filter(AppLogEntry.timestamp <= end_date)
    return q.order_by(AppLogEntry.timestamp.asc()).all()
