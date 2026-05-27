"""
PDPA ROPA Router — บันทึกรายการกิจกรรมการประมวลผลข้อมูลส่วนบุคคล
ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562
"""
import os
import json
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, UserRole, App, AppPdpa, PdpaStatus, PdpaConsent
from app.schemas import PdpaUpdate, PdpaResponse, PdpaScanResult, RopaExportResponse, PrivacyNoticeUpdate, PrivacyNoticeResponse
from app.middleware.auth import get_current_user, require_role
from app.services.audit_service import create_audit_log
from app.services.pdpa_service import scan_app_for_pii, generate_ropa_markdown
from app.services.ntp_service import ntp_service
from app.config import settings

EXPORTS_DIR = os.path.join(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), "exports")

router = APIRouter(prefix="/api/pdpa", tags=["PDPA"])


def _compute_status(pdpa: AppPdpa) -> PdpaStatus:
    """Compute PDPA status based on filled fields."""
    pii = json.loads(pdpa.pii_fields or "[]")
    has_purpose = bool(pdpa.purpose and pdpa.purpose.strip())
    has_pii = len(pii) > 0
    has_retention = bool(pdpa.retention_period and pdpa.retention_period.strip())

    if has_purpose and has_pii and has_retention:
        return PdpaStatus.COMPLETE
    elif has_purpose or has_pii or has_retention:
        return PdpaStatus.PARTIAL
    return PdpaStatus.NOT_STARTED


def _pdpa_to_response(pdpa: AppPdpa, app: App) -> dict:
    """Convert AppPdpa model to response dict."""
    return {
        "id": pdpa.id,
        "app_id": pdpa.app_id,
        "app_name": app.name,
        "app_slug": app.slug,
        "purpose": pdpa.purpose or "",
        "pii_fields": json.loads(pdpa.pii_fields or "[]"),
        "pii_auto_detected": json.loads(pdpa.pii_auto_detected or "[]"),
        "retention_period": pdpa.retention_period or "",
        "has_masking": pdpa.has_masking,
        "masking_details": pdpa.masking_details or "",
        "security_notes": pdpa.security_notes or "",
        "status": pdpa.status.value if hasattr(pdpa.status, 'value') else pdpa.status,
        "privacy_notice_enabled": pdpa.privacy_notice_enabled or False,
        "privacy_notice_title": pdpa.privacy_notice_title or "",
        "privacy_notice_detail": pdpa.privacy_notice_detail or "",
        "privacy_policy_url": pdpa.privacy_policy_url or "",
        "privacy_notice_url": pdpa.privacy_notice_url or "",
        "updated_by": pdpa.updated_by,
        "created_at": pdpa.created_at,
        "updated_at": pdpa.updated_at,
    }


@router.get("", response_model=list[PdpaResponse])
async def list_pdpa_records(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get PDPA/ROPA records for all apps."""
    apps = db.query(App).order_by(App.created_at.desc()).all()
    result = []

    for app in apps:
        pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app.id).first()
        if not pdpa:
            # Auto-create empty PDPA record
            pdpa = AppPdpa(app_id=app.id)
            db.add(pdpa)
            db.commit()
            db.refresh(pdpa)
        result.append(_pdpa_to_response(pdpa, app))

    return result


@router.get("/{app_id}", response_model=PdpaResponse)
async def get_pdpa_record(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get PDPA record for a specific app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not pdpa:
        pdpa = AppPdpa(app_id=app_id)
        db.add(pdpa)
        db.commit()
        db.refresh(pdpa)

    return _pdpa_to_response(pdpa, app)


@router.put("/{app_id}", response_model=PdpaResponse)
async def update_pdpa_record(
    app_id: int,
    data: PdpaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update PDPA record for an app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not pdpa:
        pdpa = AppPdpa(app_id=app_id)
        db.add(pdpa)
        db.flush()

    if data.purpose is not None:
        pdpa.purpose = data.purpose
    if data.pii_fields is not None:
        pdpa.pii_fields = json.dumps(data.pii_fields, ensure_ascii=False)
    if data.retention_period is not None:
        pdpa.retention_period = data.retention_period
    if data.security_notes is not None:
        pdpa.security_notes = data.security_notes

    pdpa.updated_by = user.id
    pdpa.status = _compute_status(pdpa)

    create_audit_log(
        db, request, user=user, action="update_pdpa", resource_type="app",
        resource_id=str(app_id),
        details=f"Updated PDPA record for {app.name}, status: {pdpa.status.value}",
    )
    db.commit()
    db.refresh(pdpa)

    return _pdpa_to_response(pdpa, app)


@router.post("/{app_id}/scan", response_model=PdpaScanResult)
async def scan_app_pii(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Scan an app's source code for PII fields and masking patterns."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    source_path = app.source_path
    if not source_path or not os.path.isdir(source_path):
        raise HTTPException(status_code=400, detail="App source not found on disk")

    # Run PII scan
    result = scan_app_for_pii(source_path)

    # Save auto-detected results to the PDPA record
    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not pdpa:
        pdpa = AppPdpa(app_id=app_id)
        db.add(pdpa)
        db.flush()

    pdpa.pii_auto_detected = json.dumps(result["pii_fields"], ensure_ascii=False)
    pdpa.has_masking = result["masking_detected"]
    pdpa.masking_details = "\n".join(result["masking_patterns"][:10])

    create_audit_log(
        db, request, user=user, action="scan_pdpa", resource_type="app",
        resource_id=str(app_id),
        details=f"PII scan: {len(result['pii_fields'])} categories found, masking: {result['masking_detected']}, files: {result['files_scanned']}",
    )
    db.commit()

    return PdpaScanResult(
        app_id=app_id,
        app_name=app.name,
        pii_fields_detected=result["pii_fields"],
        masking_detected=result["masking_detected"],
        masking_patterns=result["masking_patterns"],
        files_scanned=result["files_scanned"],
        scan_details=result["scan_details"],
    )


@router.post("/scan-all")
async def scan_all_apps(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Scan all deployed apps for PII fields."""
    apps = db.query(App).all()
    results = []

    for app in apps:
        if not app.source_path or not os.path.isdir(app.source_path):
            results.append({
                "app_id": app.id,
                "app_name": app.name,
                "pii_fields_detected": [],
                "masking_detected": False,
                "files_scanned": 0,
                "error": "Source not found",
            })
            continue

        result = scan_app_for_pii(app.source_path)

        # Save to DB
        pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app.id).first()
        if not pdpa:
            pdpa = AppPdpa(app_id=app.id)
            db.add(pdpa)
            db.flush()

        pdpa.pii_auto_detected = json.dumps(result["pii_fields"], ensure_ascii=False)
        pdpa.has_masking = result["masking_detected"]
        pdpa.masking_details = "\n".join(result["masking_patterns"][:10])

        results.append({
            "app_id": app.id,
            "app_name": app.name,
            "pii_fields_detected": result["pii_fields"],
            "masking_detected": result["masking_detected"],
            "files_scanned": result["files_scanned"],
        })

    create_audit_log(
        db, request, user=user, action="scan_all_pdpa", resource_type="system",
        details=f"Scanned {len(apps)} apps for PII fields",
    )
    db.commit()

    return {"apps_scanned": len(apps), "results": results}


@router.post("/export", response_model=RopaExportResponse)
async def export_ropa_report(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Export ROPA report as Markdown file."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    apps = db.query(App).order_by(App.created_at.desc()).all()
    apps_data = []

    for app in apps:
        pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app.id).first()
        pii_fields = json.loads(pdpa.pii_fields) if pdpa and pdpa.pii_fields else []
        # If no manual PII, use auto-detected
        if not pii_fields and pdpa and pdpa.pii_auto_detected:
            pii_fields = json.loads(pdpa.pii_auto_detected)

        apps_data.append({
            "app_name": app.name,
            "purpose": pdpa.purpose if pdpa else "",
            "pii_fields": pii_fields,
            "usage": app.name,
            "retention_period": pdpa.retention_period if pdpa else "",
            "has_masking": pdpa.has_masking if pdpa else False,
            "security_notes": pdpa.security_notes if pdpa else "",
        })

    ntp_info = ntp_service.get_status()
    report = generate_ropa_markdown(apps_data, ntp_info, user.username)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"ropa_report_{timestamp}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    sha256 = hashlib.sha256(report.encode("utf-8")).hexdigest()

    create_audit_log(
        db, request, user=user, action="export_ropa", resource_type="system",
        details=f"ROPA report exported: {filename}, {len(apps_data)} apps, SHA-256: {sha256[:16]}...",
        log_level="WARNING",
    )
    db.commit()

    return RopaExportResponse(
        filename=filename,
        sha256_hash=sha256,
        download_url=f"/api/pdpa/export/{filename}",
        record_count=len(apps_data),
    )


@router.get("/export/{filename}")
async def download_ropa_report(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download a generated ROPA report."""
    filepath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(path=filepath, filename=filename, media_type="text/markdown")


# ── Privacy Notice ──

@router.get("/{app_id}/privacy-notice", response_model=PrivacyNoticeResponse)
async def get_privacy_notice(
    app_id: int,
    db: Session = Depends(get_db),
):
    """Get Privacy Notice for an app (public — no auth required for popup display)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not pdpa:
        return PrivacyNoticeResponse(app_id=app_id, app_name=app.name, app_slug=app.slug)

    return PrivacyNoticeResponse(
        app_id=app_id,
        app_name=app.name,
        app_slug=app.slug,
        privacy_notice_enabled=pdpa.privacy_notice_enabled or False,
        privacy_notice_title=pdpa.privacy_notice_title or "",
        privacy_notice_detail=pdpa.privacy_notice_detail or "",
        privacy_policy_url=pdpa.privacy_policy_url or "",
        privacy_notice_url=pdpa.privacy_notice_url or "",
    )


@router.get("/privacy-notice/by-slug/{slug}", response_model=PrivacyNoticeResponse)
async def get_privacy_notice_by_slug(
    slug: str,
    db: Session = Depends(get_db),
):
    """Get Privacy Notice by app slug (public — for proxy/iframe popup)."""
    app = db.query(App).filter(App.slug == slug).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app.id).first()
    if not pdpa:
        return PrivacyNoticeResponse(app_id=app.id, app_name=app.name, app_slug=app.slug)

    return PrivacyNoticeResponse(
        app_id=app.id,
        app_name=app.name,
        app_slug=app.slug,
        privacy_notice_enabled=pdpa.privacy_notice_enabled or False,
        privacy_notice_title=pdpa.privacy_notice_title or "",
        privacy_notice_detail=pdpa.privacy_notice_detail or "",
        privacy_policy_url=pdpa.privacy_policy_url or "",
        privacy_notice_url=pdpa.privacy_notice_url or "",
    )


@router.put("/{app_id}/privacy-notice", response_model=PrivacyNoticeResponse)
async def update_privacy_notice(
    app_id: int,
    data: PrivacyNoticeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update Privacy Notice settings for an app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not pdpa:
        pdpa = AppPdpa(app_id=app_id)
        db.add(pdpa)
        db.flush()

    if data.privacy_notice_enabled is not None:
        pdpa.privacy_notice_enabled = data.privacy_notice_enabled
    if data.privacy_notice_title is not None:
        pdpa.privacy_notice_title = data.privacy_notice_title
    if data.privacy_notice_detail is not None:
        pdpa.privacy_notice_detail = data.privacy_notice_detail
    if data.privacy_policy_url is not None:
        pdpa.privacy_policy_url = data.privacy_policy_url
    if data.privacy_notice_url is not None:
        pdpa.privacy_notice_url = data.privacy_notice_url

    pdpa.updated_by = user.id

    action_label = "enabled" if pdpa.privacy_notice_enabled else "disabled"
    create_audit_log(
        db, request, user=user, action="update_privacy_notice", resource_type="app",
        resource_id=str(app_id),
        details=f"Privacy Notice {action_label} for {app.name}",
    )
    db.commit()
    db.refresh(pdpa)

    return PrivacyNoticeResponse(
        app_id=app_id,
        app_name=app.name,
        app_slug=app.slug,
        privacy_notice_enabled=pdpa.privacy_notice_enabled or False,
        privacy_notice_title=pdpa.privacy_notice_title or "",
        privacy_notice_detail=pdpa.privacy_notice_detail or "",
        privacy_policy_url=pdpa.privacy_policy_url or "",
        privacy_notice_url=pdpa.privacy_notice_url or "",
    )


# ============================================================
# PDPA Consent — per-user, per-app accept/decline tracking
# ============================================================
# §19 of the PDPA requires a record of consent (when, by whom, what was
# accepted) AND that the user can withdraw consent as easily as they
# granted it. We store each decision as its own row so the trail is
# preserved; the latest row for a (user, app) is the active decision.
# ============================================================


def _notice_version_hash(pdpa: AppPdpa) -> str:
    """Hash of the notice content the user actually saw — lets us tell later
    whether the consented-to notice is still the live one."""
    text = (
        (pdpa.privacy_notice_title or "")
        + "|"
        + (pdpa.privacy_notice_detail or "")
        + "|"
        + (pdpa.privacy_policy_url or "")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _client_ip(request: Request):
    """Honor X-Forwarded-For if present (proxy / Caddy), otherwise direct."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/{app_id}/consent")
async def record_consent(
    app_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record an accept/decline decision for the current user on this app.

    Body: { "decision": "accepted" | "declined" }

    Each call inserts a new row, so changing one's mind later doesn't
    overwrite the historical record — required for the §19 evidence
    trail. The frontend treats the latest row as the active decision.
    """
    decision = (payload or {}).get("decision", "").strip().lower()
    if decision not in ("accepted", "declined"):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'accepted' or 'declined'",
        )

    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    notice_version = _notice_version_hash(pdpa) if pdpa else None

    consent = PdpaConsent(
        user_id=user.id,
        app_id=app_id,
        decision=decision,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        notice_version=notice_version,
    )
    db.add(consent)
    create_audit_log(
        db, request, user=user, action=f"pdpa_consent_{decision}",
        resource_type="app", resource_id=str(app_id),
        details=f"PDPA consent {decision} for app {app.name} (notice v={notice_version})",
        log_level="INFO",
    )
    db.commit()
    db.refresh(consent)
    return {
        "id": consent.id,
        "decision": consent.decision,
        "app_id": app_id,
        "notice_version": notice_version,
        "created_at": consent.created_at.isoformat() if consent.created_at else None,
    }


@router.get("/{app_id}/consent")
async def get_my_consent(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the current user's latest consent decision for one app.

    Used to populate the "review" mode of the popup so the user sees
    their current choice before changing it.
    """
    latest = (
        db.query(PdpaConsent)
        .filter(PdpaConsent.user_id == user.id, PdpaConsent.app_id == app_id)
        .order_by(PdpaConsent.created_at.desc())
        .first()
    )
    if not latest:
        return {"decision": None, "created_at": None}
    return {
        "id": latest.id,
        "decision": latest.decision,
        "created_at": latest.created_at.isoformat() if latest.created_at else None,
        "notice_version": latest.notice_version,
    }


@router.get("/consents/mine")
async def list_my_consents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the current user's latest decision across every app that has
    a Privacy Notice configured. Used for an "all my consents" view."""
    # Latest consent per app
    sub = (
        db.query(
            PdpaConsent.app_id.label("app_id"),
            func.max(PdpaConsent.created_at).label("ts"),
        )
        .filter(PdpaConsent.user_id == user.id)
        .group_by(PdpaConsent.app_id)
        .subquery()
    )
    rows = (
        db.query(PdpaConsent, App)
        .join(sub, (PdpaConsent.app_id == sub.c.app_id) & (PdpaConsent.created_at == sub.c.ts))
        .join(App, App.id == PdpaConsent.app_id)
        .filter(PdpaConsent.user_id == user.id)
        .order_by(PdpaConsent.created_at.desc())
        .all()
    )
    return [
        {
            "app_id": app.id,
            "app_name": app.name,
            "app_slug": app.slug,
            "decision": consent.decision,
            "created_at": consent.created_at.isoformat() if consent.created_at else None,
            "notice_version": consent.notice_version,
        }
        for consent, app in rows
    ]
