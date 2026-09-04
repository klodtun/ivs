"""
PDPA ROPA Router — บันทึกรายการกิจกรรมการประมวลผลข้อมูลส่วนบุคคล
ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562
"""
import os
import json
import hashlib
import logging
from typing import Optional
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
from app.services import field_policy_service as field_policy
from app.services import ropa_service
from app.models import AppFieldPolicy, FieldAction
from app.services.ntp_service import ntp_service
from app.config import settings

EXPORTS_DIR = os.path.join(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), "exports")

router = APIRouter(prefix="/api/pdpa", tags=["PDPA"])
logger = logging.getLogger(__name__)


@router.get("/password-policy")
async def get_password_policy(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """The password policy (Policy-as-Code). Readable by any user so the
    user-management form can display the requirements."""
    from app.services import password_policy
    return password_policy.get_policy(db)


@router.put("/password-policy")
async def update_password_policy(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    from app.services import password_policy
    policy = password_policy.set_policy(db, payload or {})
    create_audit_log(
        db, request, user=user, action="update_password_policy", resource_type="system",
        details=f"Password policy updated: {policy}", log_level="WARNING",
    )
    db.commit()
    return policy


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


def _pdpa_to_response(pdpa: AppPdpa, app: Optional[App]) -> dict:
    """Convert AppPdpa model to response dict.

    `app` เป็น None ได้เมื่อแอปถูกลบไปแล้ว — บันทึก ROPA ยังอยู่ ชื่อจึงมาจาก
    สำเนาที่ประทับไว้ตอนลบ ไม่ใช่จากตาราง apps ที่ไม่มีแถวนั้นแล้ว
    """
    removed = getattr(pdpa, "app_removed_at", None)
    return {
        "id": pdpa.id,
        "app_id": pdpa.app_id,
        "app_name": app.name if app else (getattr(pdpa, "app_name_at_removal", "") or f"app#{pdpa.app_id}"),
        "app_slug": app.slug if app else (getattr(pdpa, "app_slug_at_removal", "") or ""),
        "app_removed_at": removed,
        "purpose": pdpa.purpose or "",
        "pii_fields": json.loads(pdpa.pii_fields or "[]"),
        "pii_auto_detected": json.loads(pdpa.pii_auto_detected or "[]"),
        "retention_period": pdpa.retention_period or "",
        "has_masking": pdpa.has_masking,
        "masking_details": pdpa.masking_details or "",
        "anonymization_mode": getattr(pdpa, "anonymization_mode", None) or "none",
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
    """บันทึกรายการกิจกรรมการประมวลผล — รวมแอปที่ถูกลบไปแล้ว

    ROPA ไม่ถูกล้างและไม่ถูกลบ รายการสะสมต่อไปเรื่อย ๆ แอปที่ถูกถอดออกจาก iVS
    ยังปรากฏอยู่พร้อมหมายเหตุว่าถูกลบเมื่อไร เพราะ PDPA ไม่ได้สั่งให้ลบบันทึกนี้
    และการถอดแอปไม่ได้ย้อนความจริงที่ว่าเคยมีการประมวลผลข้อมูลของใครบางคน

    เรียงตามลำดับที่บันทึกถูกสร้าง ไม่ใช่ตามวันที่แอปถูกสร้าง เพื่อให้ลำดับใน
    เอกสารคงที่ตลอด — แถวที่มีอยู่แล้วจะไม่ขยับเมื่อมีแอปใหม่เข้ามา
    """
    apps = {a.id: a for a in db.query(App).all()}
    result = []

    for app_id, app in sorted(apps.items()):
        if not db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first():
            db.add(AppPdpa(app_id=app_id))
    db.commit()

    for pdpa in db.query(AppPdpa).order_by(AppPdpa.id).all():
        result.append(_pdpa_to_response(pdpa, apps.get(pdpa.app_id)))

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
    if data.anonymization_mode is not None:
        mode = data.anonymization_mode if data.anonymization_mode in ("none", "anonymous", "pseudonymous") else "none"
        pdpa.anonymization_mode = mode
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


@router.get("/{app_id}/anonymization-prompt")
async def anonymization_prompt(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Generate a copy-paste AI prompt that tells the developer's AI how to
    anonymize / pseudonymize this app's PII when it exports data or exposes
    an API. Used when the app has PII but no anonymization policy is set —
    Policy-as-Code turns the gap into an actionable fix."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    pdpa = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()

    detected = json.loads(pdpa.pii_auto_detected or "[]") if pdpa else []
    confirmed = json.loads(pdpa.pii_fields or "[]") if pdpa else []
    fields = confirmed or detected
    field_list = ", ".join(fields) if fields else "personal data fields (email, phone, national ID, name, address)"

    anonymous = (
        f"You are editing the source of the app \"{app.name}\".\n"
        f"Before ANY data export (CSV/JSON/report) or API response, ANONYMIZE "
        f"these fields so an individual can no longer be identified: {field_list}.\n"
        "Rules (irreversible anonymization, PDPA/GDPR):\n"
        "- Emails -> keep only the domain, drop the local part (a@x.com -> ***@x.com)\n"
        "- Phone / national ID -> replace with [REDACTED]\n"
        "- Names / addresses -> replace with a generic label (Person_1, Region_A)\n"
        "- Do NOT keep any reversible mapping table.\n"
        "Add one function apply_before_export(record) and call it on every "
        "export path and API serializer. Show the diff."
    )
    pseudonymous = (
        f"You are editing the source of the app \"{app.name}\".\n"
        f"Before ANY data export or API response, PSEUDONYMIZE these fields: {field_list}.\n"
        "Rules (reversible only with a secret key, PDPA/GDPR pseudonymisation):\n"
        "- Replace each identifier with HMAC-SHA256(value, SECRET_KEY) -> a stable token\n"
        "- The same input must always map to the same token (so records can be "
        "correlated) but the original must not be recoverable without SECRET_KEY\n"
        "- Read SECRET_KEY from an environment variable; never hardcode it.\n"
        "Add pseudonymize(record) and call it on every export path and API "
        "serializer. Show the diff."
    )

    return {
        "app_id": app_id,
        "app_name": app.name,
        "detected_fields": fields,
        "current_mode": getattr(pdpa, "anonymization_mode", "none") if pdpa else "none",
        "prompts": {"anonymous": anonymous, "pseudonymous": pseudonymous},
    }


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

    # Run PII scan (time-bounded; never let it hang the request)
    try:
        result = scan_app_for_pii(source_path)
    except Exception as e:
        logger.warning(f"PII scan failed for app {app_id}: {e}")
        return PdpaScanResult(
            app_id=app_id, app_name=app.name, status="failed",
            scan_message=str(e)[:200],
        )

    status = result.get("status", "ok")
    msg = ""
    if status == "timeout":
        msg = f"Scan hit the time limit after {result['files_scanned']} files — results may be partial. Try again."

    # Save auto-detected results to the PDPA record (even if partial)
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
        details=f"PII scan [{status}]: {len(result['pii_fields'])} categories, masking: {result['masking_detected']}, files: {result['files_scanned']}",
        log_level="WARNING" if status != "ok" else "INFO",
    )
    db.commit()

    return PdpaScanResult(
        app_id=app_id,
        app_name=app.name,
        status=status,
        scan_message=msg,
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
    """ส่งออกบันทึกรายการกิจกรรมการประมวลผลเป็นไฟล์ Markdown

    รวมกิจกรรมของแอปที่ถูกลบไปแล้วด้วย เดินจากตาราง ROPA ไม่ใช่จากตาราง apps
    เดิมเดินจาก apps ทำให้รายงานที่ส่งถึงผู้ตรวจตกกิจกรรมของระบบที่ปลดไปแล้ว
    ทั้งหมด — ซึ่งเป็นคำถามที่ผู้ตรวจถามพอดี และเป็นสิ่งที่กฎใน OPERATIONS.md
    ห้ามไว้ ("ROPA is never cleared")

    เรียงตาม id ของบันทึก เพื่อให้ลำดับในรายงานที่ออกไปแล้วยังชี้แถวเดิมเสมอ
    """
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    apps = {a.id: a for a in db.query(App).all()}
    apps_data = []

    for pdpa in db.query(AppPdpa).order_by(AppPdpa.id).all():
        app = apps.get(pdpa.app_id)
        removed_at = getattr(pdpa, "app_removed_at", None)
        name = app.name if app else (
            getattr(pdpa, "app_name_at_removal", "") or f"app#{pdpa.app_id}")

        pii_fields = json.loads(pdpa.pii_fields) if pdpa.pii_fields else []
        # If no manual PII, use auto-detected
        if not pii_fields and pdpa.pii_auto_detected:
            pii_fields = json.loads(pdpa.pii_auto_detected)

        apps_data.append({
            "app_name": name,
            # แอปถูกลบแล้ว แต่บันทึกยังอยู่ — รายงานต้องบอกให้ผู้อ่านรู้ว่ากิจกรรมนี้
            # เลิกทำแล้วเมื่อไร ไม่ใช่ปล่อยให้เข้าใจว่ายังดำเนินอยู่
            "removed_at": removed_at.isoformat() if removed_at else "",
            "purpose": pdpa.purpose or "",
            "pii_fields": pii_fields,
            "usage": name,
            "retention_period": pdpa.retention_period or "",
            "has_masking": pdpa.has_masking,
            "security_notes": pdpa.security_notes or "",
            # ฐานการประมวลผลและผู้รับข้อมูล — ROPA ที่ไม่ระบุสองอย่างนี้
            # ไม่ครบตามที่ผู้ควบคุมข้อมูลต้องจัดทำ
            "legal_basis": (pdpa.legal_basis or ""),
            "recipients": ropa_service.get_recipients(pdpa),
            "erasure": ropa_service.erasure_decision(pdpa),
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


# ── Field-level policy (policy as code) ──────────────────────────────
#
# The PII scan says which fields hold personal data; these endpoints turn that
# into rules the exchange layer enforces on every response. Until this existed,
# opening an app's API meant opening whatever the app happened to return.


@router.get("/{app_id}/field-policy")
async def get_field_policy(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Field rules for this app, unreviewed ones first."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return field_policy.summary(db, app_id)


@router.post("/{app_id}/field-policy/derive")
async def derive_field_policy(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Scan the app and draft a rule for every field found that has none.

    Existing rules are kept as they are — a later scan must never quietly
    reverse a decision someone already made.
    """
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not app.source_path or not os.path.isdir(app.source_path):
        raise HTTPException(status_code=400, detail="App source not found on disk")

    try:
        scan = scan_app_for_pii(app.source_path)
    except Exception as e:
        logger.warning(f"PII scan failed for app {app_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)[:200]}")

    result = field_policy.derive_from_scan(db, app_id, scan)
    create_audit_log(
        db, request, user=user, action="derive_field_policy", resource_type="pdpa",
        resource_id=str(app_id),
        details=(
            f"{app.name}: สร้างกฎรายฟิลด์จากผลสแกน {result['created']} ฟิลด์ใหม่ "
            f"(คงของเดิม {result['kept']}) รอตรวจสอบ {result['pending_review']}"
        ),
    )
    db.commit()
    return result


@router.put("/{app_id}/field-policy")
async def confirm_field_policy(
    app_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Confirm one field's rule. Body: {field_name, action, note?}."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    field_name = (payload.get("field_name") or "").strip()
    action_raw = (payload.get("action") or "").strip()
    if not field_name:
        raise HTTPException(status_code=422, detail="field_name is required")
    try:
        action = FieldAction(action_raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="action must be block, mask or allow")

    row = field_policy.confirm(
        db, app_id, field_name, action, user.id, payload.get("note") or ""
    )
    create_audit_log(
        db, request, user=user, action="confirm_field_policy", resource_type="pdpa",
        resource_id=str(app_id),
        details=f"{app.name}: ฟิลด์ {field_name} ตั้งเป็น {action.value}",
        # Widening access is the decision worth finding later, so it is logged
        # at a level that stands out in the audit view.
        log_level="WARNING" if action == FieldAction.ALLOW else "INFO",
    )
    db.commit()
    return {
        "field_name": row.field_name,
        "action": row.action.value,
        "confirmed": bool(row.confirmed),
    }


@router.post("/{app_id}/field-policy/preview")
async def preview_field_policy(
    app_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Run a sample payload through the rules and show what would leave.

    Reviewing a list of field names tells you very little; seeing the actual
    response with the national ID gone and the email replaced tells you exactly
    what the rules do before anything is opened up.
    """
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    sample = payload.get("sample")
    if sample is None:
        raise HTTPException(status_code=422, detail="sample is required")

    filtered, applied = field_policy.apply_policy(db, app_id, sample)
    return {"result": filtered, "applied": applied}


# ── ROPA: ผู้รับข้อมูล ฐานการประมวลผล และสิทธิขอให้ลบ ────────────────
#
# One app is one processing activity. Opening an API or an MCP tool adds a
# recipient to that activity, which has to show up both here and in the privacy
# notice — a recipient the data subject was never told about is the problem.


@router.get("/{app_id}/ropa")
async def get_ropa_detail(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Lawful basis, recipients, and what a deletion request would get."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    return {
        "app_id": app_id,
        "app_name": app.name,
        "legal_basis": record.legal_basis if record else "",
        "erasure_right": (record.erasure_right if record else "auto") or "auto",
        "erasure_note": (record.erasure_note if record else "") or "",
        "recipients": ropa_service.get_recipients(record) if record else [],
        "erasure": ropa_service.erasure_decision(record),
        "basis_options": ropa_service.basis_options(),
    }


@router.put("/{app_id}/ropa")
async def update_ropa_detail(
    app_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set the lawful basis and the erasure rule for this activity.

    Body: {legal_basis?, erasure_right?, erasure_note?}
    """
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not record:
        record = AppPdpa(app_id=app_id)
        db.add(record)
        db.flush()

    if "legal_basis" in payload:
        basis = (payload.get("legal_basis") or "").strip()
        if basis and basis not in ropa_service.LEGAL_BASIS:
            raise HTTPException(status_code=422, detail="Unknown legal basis")
        record.legal_basis = basis
    if "erasure_right" in payload:
        setting = (payload.get("erasure_right") or "auto").strip()
        if setting not in ("auto", "allowed", "restricted"):
            raise HTTPException(status_code=422, detail="erasure_right must be auto, allowed or restricted")
        # An override is what gets quoted back to the person who asked, so it
        # cannot be a bare switch with no explanation behind it.
        if setting != "auto" and not (payload.get("erasure_note") or record.erasure_note or "").strip():
            raise HTTPException(
                status_code=422,
                detail="ต้องระบุเหตุผลเมื่อกำหนดสิทธิการลบเอง เพราะเหตุผลนี้จะถูกแจ้งกลับไปยังเจ้าของข้อมูล",
            )
        record.erasure_right = setting
    if "erasure_note" in payload:
        record.erasure_note = (payload.get("erasure_note") or "")[:2000]

    db.commit()
    db.refresh(record)
    decision = ropa_service.erasure_decision(record)
    create_audit_log(
        db, request, user=user, action="update_ropa", resource_type="pdpa",
        resource_id=str(app_id),
        details=(
            f"{app.name}: ฐานการประมวลผล {record.legal_basis or '-'} · "
            f"สิทธิขอให้ลบ {'ได้' if decision['erasable'] else 'ไม่ได้'} ({record.erasure_right})"
        ),
        log_level="WARNING",
    )
    db.commit()
    return {
        "legal_basis": record.legal_basis,
        "erasure_right": record.erasure_right,
        "erasure_note": record.erasure_note,
        "erasure": decision,
    }


@router.post("/{app_id}/ropa/recipients")
async def add_ropa_recipient(
    app_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Record a recipient of this activity's data. Body: {kind, name, purpose?, note?}."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not record:
        record = AppPdpa(app_id=app_id)
        db.add(record)
        db.flush()

    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    added, recipients = ropa_service.add_recipient(
        db, record, payload.get("kind") or "external", name,
        payload.get("purpose") or "", payload.get("note") or "",
    )
    if added:
        create_audit_log(
            db, request, user=user, action="ropa_add_recipient", resource_type="pdpa",
            resource_id=str(app_id),
            details=f"{app.name}: เพิ่มผู้รับข้อมูล {name} — ต้องปรากฏในประกาศแจ้งเตือนด้วย",
            log_level="WARNING",
        )
        db.commit()
    return {"added": added, "recipients": recipients}


@router.delete("/{app_id}/ropa/recipients")
async def remove_ropa_recipient(
    app_id: int,
    request: Request,
    kind: str,
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="No ROPA record for this app")
    recipients = ropa_service.remove_recipient(db, record, kind, name)
    create_audit_log(
        db, request, user=user, action="ropa_remove_recipient", resource_type="pdpa",
        resource_id=str(app_id), details=f"ลบผู้รับข้อมูล {name}", log_level="WARNING",
    )
    db.commit()
    return {"recipients": recipients}


@router.get("/{app_id}/erasure-check")
async def erasure_check(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """Answer a deletion request for this activity, with the reason to send back.

    A data subject names the activity; this says whether the right applies to it
    and why. Deleting data held under a legal obligation would be the violation,
    so the answer comes from the recorded basis, not from discretion.
    """
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    return ropa_service.erasure_decision(record)
