"""
e-Contract certificate endpoints — issue and verify integrity + trusted-time
certificates for electronic documents/contracts.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, EContractCert
from app.middleware.auth import require_role, get_current_user
from app.services import econtract_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/econtract", tags=["e-Contract"])
logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024  # 25 MB per document


@router.get("")
async def list_certs(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    rows = db.query(EContractCert).order_by(EContractCert.created_at.desc()).limit(100).all()
    return [econtract_service.to_dict(r) for r in rows]


@router.post("/certify")
async def certify(
    request: Request,
    file: UploadFile = File(...),
    signer: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Issue an integrity + trusted-timestamp certificate for an uploaded file."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="ไฟล์ว่าง")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="ไฟล์ใหญ่เกิน 25 MB")

    cert = econtract_service.certify(
        db, filename=file.filename or "document",
        data=data, signer=signer or user.username, note=note,
        created_by=user.id,
    )
    create_audit_log(
        db, request, user=user, action="econtract_certify", resource_type="econtract",
        resource_id=cert["cert_id"],
        details=f"ออกใบรับรอง {cert['cert_id']} · {cert['filename']} · SHA-256 {cert['sha256'][:16]}…",
    )
    db.commit()
    return cert


@router.post("/verify")
async def verify(
    file: UploadFile = File(None),
    cert_id: str = Form(""),
    sha256: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """Verify a document against its certificate. Provide the file (hashed
    server-side) and/or a cert_id/sha256."""
    if file is not None:
        data = await file.read()
        if data:
            import hashlib
            sha256 = hashlib.sha256(data).hexdigest()
    if not sha256 and not cert_id:
        raise HTTPException(status_code=422, detail="ต้องระบุไฟล์ หรือ cert_id")
    return econtract_service.verify(db, sha256=sha256, cert_id=cert_id)


@router.get("/{cert_id}")
async def get_detail(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Certificate detail + its electronic signatures."""
    d = econtract_service.detail(db, cert_id)
    if not d:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    return d


@router.post("/{cert_id}/sign")
async def sign(
    cert_id: str,
    request: Request,
    signer_name: str = Form(...),
    method: str = Form("typed"),
    identity_ref: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Record an electronic signature on a certificate (§9/§26)."""
    if not signer_name.strip():
        raise HTTPException(status_code=422, detail="ต้องระบุชื่อผู้ลงนาม")
    ip = request.client.host if request.client else ""
    try:
        sig = econtract_service.add_signature(
            db, cert_id=cert_id, signer_name=signer_name.strip(),
            method=method, identity_ref=identity_ref, ip=ip, created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_sign", resource_type="econtract",
        resource_id=cert_id,
        details=f"ลงนาม {cert_id} โดย {signer_name.strip()} · วิธี {method}",
    )
    db.commit()
    return sig


@router.get("/{cert_id}/download")
async def download_cert(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Download the certificate as a self-contained JSON evidence file."""
    row = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    cert = econtract_service.to_dict(row)
    cert["_note"] = (
        "ใบรับรองเวลาและความครบถ้วนของเอกสารอิเล็กทรอนิกส์ (iVS e-Contract). "
        "ตรวจสอบได้ที่เมนู e-Contract → ตรวจสอบ โดยใช้ cert_id หรืออัปโหลดไฟล์เดิม."
    )
    body = json.dumps(cert, ensure_ascii=False, indent=2)
    return Response(
        content=body, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{cert_id}.json"'},
    )
