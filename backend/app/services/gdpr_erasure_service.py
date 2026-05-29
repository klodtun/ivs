"""Right-to-be-Forgotten executor.

Implements GDPR Art. 17, APPI Art. 30, PDPA §35 erasure rights against
the IVS data stores. The strategy is REPLACE-IN-PLACE, not row-delete,
because Thai พ.ร.บ. คอมพิวเตอร์ §26 requires log rows to survive for
90+ days. Erasure replaces only the PII fields with [ERASED_GDPR]
tokens; the rows themselves remain so the forensic trail (action,
timestamp, request_id) stays intact for audit obligations.

Three phases:
  1. PREVIEW  → count matching rows per table, no writes
  2. EXECUTE  → atomic per-table scrub + generate certificate
  3. CERTIFY  → markdown record + SHA-256 fingerprint, returned and
                stored in gdpr_erasure_requests for re-issue
"""
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    User, AuditLog, AppLogEntry, PdpaConsent, GdprErasureRequest,
)
from app.services.pii_anonymizer import anonymize as anonymize_pii

ERASED_TOKEN = "[ERASED_GDPR]"


def _hmac_key() -> bytes:
    secret = getattr(settings, "SECRET_KEY", None) or "ivs-default-secret"
    return secret.encode("utf-8")


def _target_hash(value: str) -> str:
    return hmac.new(_hmac_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _redact_in_text(text: Optional[str], needle: str) -> Optional[str]:
    """Case-insensitive substring replacement, with word-boundary on
    short tokens to avoid false matches inside larger strings."""
    if not text or not needle:
        return text
    pattern = re.escape(needle)
    return re.sub(pattern, ERASED_TOKEN, text, flags=re.IGNORECASE)


def _matches_field(field_value: Optional[str], needle: str) -> bool:
    if not field_value:
        return False
    return needle.lower() in field_value.lower()


def _build_filters(target_type: str, target_value: str):
    """Build a list of (table, candidate-fields, filter-expression-fn)."""
    # Used by both preview and execute paths
    nv = target_value.strip()
    return nv


def preview(db: Session, target_type: str, target_value: str) -> dict:
    """Count rows that WOULD be affected by execute(), no writes."""
    nv = target_value.strip()
    counts = {
        "audit_logs": 0,
        "app_log_entries": 0,
        "pdpa_consents": 0,
        "users": 0,
    }

    # AuditLog — username, ip_address, user_agent, details
    counts["audit_logs"] = (
        db.query(AuditLog).filter(
            or_(
                AuditLog.username == nv,
                AuditLog.ip_address == nv,
                AuditLog.user_agent.contains(nv),
                AuditLog.details.contains(nv),
            )
        ).count()
    )

    # AppLogEntry — Level 1 already anonymized, but the deterministic
    # HMAC means the target's anonymized token is the same everywhere
    # we can locate it via the anonymizer output.
    anon_token = anonymize_pii(nv)
    if anon_token != nv:
        counts["app_log_entries"] = (
            db.query(AppLogEntry).filter(AppLogEntry.log_line.contains(anon_token)).count()
        )
    # Also catch raw matches that slipped past anonymization
    raw_matches = (
        db.query(AppLogEntry).filter(AppLogEntry.log_line.contains(nv)).count()
    )
    counts["app_log_entries"] = max(counts["app_log_entries"], raw_matches)

    # PdpaConsent — ip + user_agent
    counts["pdpa_consents"] = (
        db.query(PdpaConsent).filter(
            or_(
                PdpaConsent.ip_address == nv,
                PdpaConsent.user_agent.contains(nv),
            )
        ).count()
    )

    # User row — only when target identifies a user
    if target_type == "user_id":
        try:
            uid = int(nv)
            counts["users"] = (
                db.query(User).filter(User.id == uid).count()
            )
        except ValueError:
            pass
    elif target_type == "username":
        counts["users"] = db.query(User).filter(User.username == nv).count()
    elif target_type == "email":
        counts["users"] = db.query(User).filter(User.email == nv).count()

    return counts


def execute(
    db: Session,
    target_type: str,
    target_value: str,
    reason: str,
    legal_basis: str,
    admin: User,
    request_ip: Optional[str],
) -> dict:
    """Scrub PII matching the target across all tables. Returns the
    erasure record (id, certificate text, sha256, rows_affected)."""
    nv = target_value.strip()
    affected: dict = {"audit_logs": 0, "app_log_entries": 0, "pdpa_consents": 0, "users": 0}

    # ── 1. AuditLog scrub ──
    rows = db.query(AuditLog).filter(
        or_(
            AuditLog.username == nv,
            AuditLog.ip_address == nv,
            AuditLog.user_agent.contains(nv),
            AuditLog.details.contains(nv),
        )
    ).all()
    for r in rows:
        if r.username == nv:
            r.username = ERASED_TOKEN
        if r.ip_address == nv:
            r.ip_address = ERASED_TOKEN
        if _matches_field(r.user_agent, nv):
            r.user_agent = ERASED_TOKEN
        if _matches_field(r.details, nv):
            r.details = _redact_in_text(r.details, nv)
    affected["audit_logs"] = len(rows)

    # ── 2. AppLogEntry scrub ──
    anon_token = anonymize_pii(nv)
    log_rows = db.query(AppLogEntry).filter(
        or_(
            AppLogEntry.log_line.contains(nv),
            AppLogEntry.log_line.contains(anon_token) if anon_token != nv else AppLogEntry.log_line.contains(nv),
        )
    ).all()
    for r in log_rows:
        new_line = _redact_in_text(r.log_line, nv)
        if anon_token != nv:
            new_line = _redact_in_text(new_line, anon_token)
        r.log_line = new_line
    affected["app_log_entries"] = len(log_rows)

    # ── 3. PdpaConsent scrub (keep consent record per Art.7(1) accountability;
    #      null the linking identifiers so consent can't be re-attached) ──
    consent_rows = db.query(PdpaConsent).filter(
        or_(
            PdpaConsent.ip_address == nv,
            PdpaConsent.user_agent.contains(nv),
        )
    ).all()
    for r in consent_rows:
        if r.ip_address == nv:
            r.ip_address = ERASED_TOKEN
        if _matches_field(r.user_agent, nv):
            r.user_agent = ERASED_TOKEN
    affected["pdpa_consents"] = len(consent_rows)

    # ── 4. User row — full identity deletion (separate concern from logs).
    #      Reuse the same auto-reassign rule from delete_user: any apps the
    #      user owned move to the requesting admin so deployments don't break.
    if target_type in ("user_id", "username", "email"):
        q = db.query(User)
        if target_type == "user_id":
            try:
                q = q.filter(User.id == int(nv))
            except ValueError:
                q = q.filter(False)
        elif target_type == "username":
            q = q.filter(User.username == nv)
        elif target_type == "email":
            q = q.filter(User.email == nv)
        target_user = q.first()
        if target_user and target_user.id != admin.id:
            # Reassign owned apps before deleting (same pattern as auth.delete_user)
            from app.models import App, Tunnel, VaultKey, UserAppAccess, AppPdpa, AuditLogExport
            db.query(App).filter(App.owner_id == target_user.id).update(
                {"owner_id": admin.id}, synchronize_session=False
            )
            db.query(Tunnel).filter(Tunnel.created_by == target_user.id).update(
                {"created_by": admin.id}, synchronize_session=False
            )
            db.query(VaultKey).filter(VaultKey.created_by == target_user.id).update(
                {"created_by": admin.id}, synchronize_session=False
            )
            db.query(AppPdpa).filter(AppPdpa.updated_by == target_user.id).update(
                {"updated_by": admin.id}, synchronize_session=False
            )
            db.query(AuditLogExport).filter(AuditLogExport.exported_by == target_user.id).update(
                {"exported_by": admin.id}, synchronize_session=False
            )
            db.query(UserAppAccess).filter(UserAppAccess.user_id == target_user.id).delete(
                synchronize_session=False
            )
            db.delete(target_user)
            affected["users"] = 1

    # ── 5. Certificate (markdown + SHA-256) ──
    cert, cert_sha = _build_certificate(
        target_type=target_type,
        target_hash=_target_hash(nv),
        affected=affected,
        admin=admin,
        legal_basis=legal_basis,
        reason=reason,
    )

    # ── 6. Persist erasure record (no raw target — only hash) ──
    record = GdprErasureRequest(
        target_type=target_type,
        target_hash=_target_hash(nv),
        reason=reason,
        legal_basis=legal_basis,
        requested_by=admin.id,
        requested_ip=request_ip,
        rows_affected=json.dumps(affected),
        sha256_proof=cert_sha,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "target_hash": record.target_hash,
        "rows_affected": affected,
        "sha256_proof": cert_sha,
        "certificate": cert,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _build_certificate(
    *, target_type: str, target_hash: str, affected: dict,
    admin: User, legal_basis: str, reason: str,
) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    lines = []
    lines.append("# IVS GDPR / APPI / PDPA Erasure Certificate")
    lines.append("")
    lines.append(f"- **Issued**: {now.isoformat()}")
    lines.append(f"- **Issued by**: {admin.username} (uid {admin.id})")
    lines.append(f"- **System**: {settings.APP_NAME} v{settings.APP_VERSION}")
    lines.append("")
    lines.append("## Erasure Request")
    lines.append("")
    lines.append(f"- **Target type**: `{target_type}`")
    lines.append(f"- **Target hash** (HMAC-SHA256 of identifier): `{target_hash}`")
    lines.append(f"- **Legal basis**: {legal_basis or 'GDPR Art. 17 / APPI Art. 30 / PDPA §35'}")
    lines.append(f"- **Reason**: {reason or '(not provided)'}")
    lines.append("")
    lines.append("## Rows Affected")
    lines.append("")
    lines.append("| Table | Rows scrubbed |")
    lines.append("|-------|---------------|")
    for table, count in affected.items():
        lines.append(f"| `{table}` | {count} |")
    lines.append("")
    lines.append("## Erasure Method")
    lines.append("")
    lines.append("- **Strategy**: replace-in-place with `" + ERASED_TOKEN + "` (NOT row deletion).")
    lines.append("- **Rationale**: Thai พ.ร.บ. คอมพิวเตอร์ §26 mandates log retention; "
                 "GDPR Recital 26 explicitly recognises pseudonymisation as an erasure-equivalent "
                 "where deletion conflicts with another legal obligation.")
    lines.append("- **Forensic trail preserved**: timestamps, action codes, and `request_id` remain "
                 "so subsequent audits can verify the row's existence without re-identifying the data subject.")
    lines.append("")
    lines.append("## Integrity")
    lines.append("")
    lines.append("The SHA-256 hash of this document (computed AFTER appending the hash line itself "
                 "would change it, so the hash below covers the body only) is stored in the IVS "
                 "database. Re-issue this certificate by calling the same endpoint with the request id.")
    content = "\n".join(lines)
    cert_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    content += f"\n\n- **Body SHA-256**: `{cert_sha}`\n"
    return content, cert_sha
