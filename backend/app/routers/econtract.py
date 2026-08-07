"""
e-Contract certificate endpoints — issue and verify integrity + trusted-time
certificates for electronic documents/contracts.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, EContractCert
from app.middleware.auth import require_role, get_current_user
from app.services import econtract_service, profile_service, compliance_service, chain_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/econtract", tags=["e-Contract"])
logger = logging.getLogger(__name__)

MAX_BYTES = 25 * 1024 * 1024  # 25 MB per document


@router.get("")
async def list_certs(
    scope: str = "today",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """ค่าเริ่มต้นแสดงเฉพาะวันนี้ — scope=today|7d|30d|all และค้นด้วย q"""
    from sqlalchemy import func
    from app.models import EContractSignature
    query = econtract_service._scope_filter(db.query(EContractCert), scope)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            (EContractCert.cert_id.like(like)) | (EContractCert.filename.like(like))
        )
    rows = query.order_by(EContractCert.created_at.desc()).limit(200).all()
    counts = dict(
        db.query(EContractSignature.cert_id, func.count(EContractSignature.id))
        .group_by(EContractSignature.cert_id).all()
    )
    out = []
    for r in rows:
        d = econtract_service.to_dict(r)
        d["signature_count"] = counts.get(r.cert_id, 0)
        out.append(d)
    return out


# ── Contract Profiles (ชั้น 7 เรื่อง) ────────────────────────────────────

@router.get("/profiles")
async def list_profiles(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ประเภทสัญญาที่เลือกได้ + ขั้นตอนที่บังคับของแต่ละประเภท"""
    return {
        "profiles": profile_service.list_profiles(),
        "groups": profile_service.GROUP_LABELS,
        "steps": [
            {"key": k, **profile_service.STEP_META[k]} for k in profile_service.STEP_KEYS
        ],
    }


@router.get("/handbook")
async def handbook_info(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ข้อมูลคู่มือ e-Contract ของ ETDA และสถานะว่ามีไฟล์ให้ดาวน์โหลดหรือไม่"""
    return profile_service.handbook_info()


@router.get("/handbook/download")
async def handbook_download(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ดาวน์โหลดคู่มือ e-Contract (ETDA) จากสำเนาในเครื่อง — 144 หน้า

    แหล่งหลักคือลิงก์ Google Drive (ดู `GET /handbook`) ปลายทางนี้ใช้เมื่อมีสำเนา
    วางไว้ในเครื่องเท่านั้น เช่น หน่วยงานที่ไม่ต่ออินเทอร์เน็ต
    """
    info = profile_service.handbook_info()
    if not info["local_available"]:
        raise HTTPException(
            status_code=404,
            detail=(
                "ไม่มีสำเนาคู่มือในเครื่องนี้ — ใช้ลิงก์ Google Drive แทน "
                f"({info['drive_url']}) หรือวางไฟล์ '{profile_service.HANDBOOK_FILENAME}' "
                f"ไว้ที่ {profile_service.HANDBOOK_DIR} เพื่อให้ดาวน์โหลดตรงจาก iVS ได้"
            ),
        )
    create_audit_log(
        db, request, user=user, action="econtract_handbook_download",
        resource_type="econtract", resource_id="handbook",
        details=f"ดาวน์โหลดคู่มือ e-Contract (ETDA) · {info['size_bytes']} bytes",
    )
    db.commit()
    return FileResponse(
        profile_service.handbook_path(),
        media_type="application/pdf",
        filename=info["download_name"],
    )


@router.get("/profiles/{profile_key}")
async def get_profile(
    profile_key: str,
    sector: str = "",
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """โปรไฟล์ที่ resolve แล้ว (baseline + overlay ภาครัฐ ถ้าระบุ)"""
    try:
        return profile_service.resolve(profile_key, sector=sector or None)
    except profile_service.ProfileError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── e-Seal — ตราประทับนิติบุคคล (ม.9 วรรคท้าย) ───────────────────────────

@router.get("/seals")
async def list_seals(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ตราประทับนิติบุคคลที่ลงทะเบียนไว้"""
    return econtract_service.list_seals(db, include_inactive=include_inactive)


@router.post("/seals")
async def create_seal(
    request: Request,
    org_name: str = Form(...),
    org_tax_id: str = Form(""),
    image_data: str = Form(""),
    authority_note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """ลงทะเบียนตราประทับของนิติบุคคล"""
    try:
        seal = econtract_service.create_seal(
            db, org_name=org_name, org_tax_id=org_tax_id, image_data=image_data,
            authority_note=authority_note, created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_seal_create", resource_type="econtract",
        resource_id=seal["seal_id"], details=f"ลงทะเบียนตราประทับ {seal['org_name']}",
    )
    db.commit()
    return seal


@router.delete("/seals/{seal_id}")
async def deactivate_seal(
    seal_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """เลิกใช้ตราประทับ — ไม่ลบ เพราะสัญญาที่ประทับไปแล้วต้องอ้างอิงกลับได้"""
    try:
        seal = econtract_service.deactivate_seal(db, seal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_seal_deactivate", resource_type="econtract",
        resource_id=seal_id, details=f"เลิกใช้ตราประทับ {seal['org_name']}",
    )
    db.commit()
    return seal


@router.post("/{cert_id}/seal")
async def apply_seal(
    cert_id: str,
    request: Request,
    seal_id: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """ประทับตรานิติบุคคลลงบนใบรับรอง"""
    try:
        rec = econtract_service.apply_seal(
            db, cert_id=cert_id, seal_id=seal_id, note=note, applied_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_seal_apply", resource_type="econtract",
        resource_id=cert_id, details=f"ประทับตรา {seal_id} · {rec.get('actor', '')}",
    )
    db.commit()
    return rec


# ── e-Original + e-Retention ─────────────────────────────────────────────

@router.get("/originals")
async def originals(
    scope: str = "today",
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ภาพรวมความเป็นต้นฉบับ (ม.10) และการเก็บรักษา (ม.12) — ค่าเริ่มต้นเฉพาะวันนี้"""
    return econtract_service.originals_overview(db, scope=scope, q=q)


# ── PDF/A ────────────────────────────────────────────────────────────────

@router.get("/pdfa/capability")
async def pdfa_capability(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """เครื่องนี้สร้าง PDF/A ได้หรือไม่ และขาดอะไร"""
    from app.services import pdfa_service
    return pdfa_service.capability()


@router.get("/{cert_id}/final-document")
async def final_document(
    cert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """เอกสารฉบับสมบูรณ์เป็น PDF/A — ต้นฉบับ (ถ้าเก็บไว้) + ใบรับรองการลงนามต่อท้าย"""
    from app.services import pdfa_service

    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")

    # ใช้เอกสารตัวจริงที่เก็บไว้ ถ้ามี — ไม่งั้นได้เฉพาะใบรับรองการลงนาม
    source = None
    for a in econtract_service.list_attachments(db, cert_id):
        if a["kind"] == "original_document" and a["stored"]:
            try:
                path, _, _ = econtract_service.attachment_file(db, cert_id, a["id"])
                with open(path, "rb") as f:
                    source = f.read()
                break
            except ValueError:
                pass

    try:
        pdf, report = pdfa_service.build_final_document(
            cert=econtract_service.to_dict(cert),
            chain=chain_service.chain(db, cert_id),
            compliance=compliance_service.evaluate(db, cert),
            signatures=econtract_service.list_signatures(db, cert_id),
            attachments=econtract_service.list_attachments(db, cert_id),
            source_pdf=source,
        )
    except pdfa_service.PdfaUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    create_audit_log(
        db, request, user=user, action="econtract_final_document",
        resource_type="econtract", resource_id=cert_id,
        details=(f"สร้างเอกสารฉบับสมบูรณ์ PDF/A · {report.get('pages')} หน้า · "
                 f"แนบต้นฉบับ={report.get('included_source_document')}"),
    )
    db.commit()
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cert_id}_final.pdf"'},
    )


# ── Certify / Verify ─────────────────────────────────────────────────────

@router.post("/certify")
async def certify(
    request: Request,
    file: UploadFile = File(...),
    signer: str = Form(""),
    note: str = Form(""),
    profile_key: str = Form("generic"),
    sector: str = Form(""),
    convert_pdfa: str = Form("false"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Issue an integrity + trusted-timestamp certificate for an uploaded file.

    `profile_key` กำหนดว่าสัญญาชนิดนี้ต้องทำอะไรบ้างใน 7 เรื่อง — โปรไฟล์จะถูกแช่แข็ง
    ไว้กับใบรับรองเพื่อให้ประเมินย้อนหลังได้ด้วยกฎชุดเดิม
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="ไฟล์ว่าง")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="ไฟล์ใหญ่เกิน 25 MB")

    try:
        cert = econtract_service.certify(
            db, filename=file.filename or "document",
            data=data, signer=signer or user.username, note=note,
            created_by=user.id, profile_key=profile_key or "generic", sector=sector,
            convert_pdfa=str(convert_pdfa).lower() in ("1", "true", "yes", "on"),
        )
    except ValueError as e:
        # ม.3 — ธุรกรรมครอบครัว/มรดก ทำเป็นอิเล็กทรอนิกส์ไม่ได้
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_certify", resource_type="econtract",
        resource_id=cert["cert_id"],
        details=(
            f"ออกใบรับรอง {cert['cert_id']} · {cert['filename']} · "
            f"SHA-256 {cert['sha256'][:16]}… · โปรไฟล์ {cert['profile_key']} v{cert['profile_version']}"
        ),
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
    signing_mode: str = Form("remote"),
    signer_role: str = Form(""),
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
            signing_mode=signing_mode, signer_role=signer_role,
            user_agent=request.headers.get("user-agent", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_sign", resource_type="econtract",
        resource_id=cert_id,
        details=(f"ลงนาม {cert_id} โดย {signer_name.strip()} · วิธี {method} · "
                 f"{'ต่อหน้า' if signing_mode == 'in_person' else 'ระยะไกล'}"),
    )
    db.commit()
    return sig


@router.get("/{cert_id}/chain")
async def evidence_chain(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """โซ่หลักฐาน — ทุกเหตุการณ์เรียงตามลำดับ พร้อมผลตรวจความต่อเนื่อง"""
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    return chain_service.chain(db, cert_id)


@router.post("/{cert_id}/deliver")
async def record_delivery(
    cert_id: str,
    request: Request,
    recipients: str = Form(...),   # คั่นด้วย comma หรือขึ้นบรรทัดใหม่
    channel: str = Form("email"),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """บันทึกการส่งร่างให้คู่สัญญา (ไม่ใช่การยืนยันตัวตน)"""
    parts = [p for chunk in recipients.replace("\n", ",").split(",") if (p := chunk.strip())]
    try:
        link = econtract_service.record_delivery(
            db, cert_id=cert_id, recipients=parts, channel=channel,
            note=note, recorded_by=user.id,
        )
    except (ValueError, chain_service.ChainError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_deliver", resource_type="econtract",
        resource_id=cert_id, details=f"ส่งร่างให้ {len(parts)} ราย ผ่าน {channel}",
    )
    db.commit()
    return link


@router.post("/{cert_id}/acceptance")
async def record_acceptance(
    cert_id: str,
    request: Request,
    party: str = Form(...),
    source: str = Form("first_party"),
    evidence: str = Form(""),
    note: str = Form(""),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """บันทึกคำสนอง — คู่สัญญาตกลงตามร่าง (ม.13) แนบไฟล์หลักฐานได้"""
    ip = request.client.host if request.client else ""
    att = None
    try:
        # แนบหลักฐานก่อน เพื่อให้ hash ของไฟล์อยู่ในโซ่ก่อน link คำสนอง
        if file is not None:
            data = await file.read()
            if data:
                att = econtract_service.add_attachment(
                    db, cert_id=cert_id, kind="acceptance_evidence",
                    filename=file.filename or "acceptance", data=data,
                    content_type=file.content_type or "", note=note, uploaded_by=user.id,
                )
        link = econtract_service.record_acceptance(
            db, cert_id=cert_id, party=party, source=source, evidence=evidence,
            ip=ip, note=note, recorded_by=user.id,
            attachment_sha256=(att or {}).get("sha256", ""),
            attachment_filename=(att or {}).get("filename", ""),
        )
    except (ValueError, chain_service.ChainError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_acceptance", resource_type="econtract",
        resource_id=cert_id, details=f"คำสนองจาก {party} ({source})",
    )
    db.commit()
    return link


@router.get("/{cert_id}/attachments")
async def list_attachments(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """หลักฐานตัวจริงที่แนบไว้กับสัญญานี้"""
    return econtract_service.list_attachments(db, cert_id)


@router.post("/{cert_id}/attachments")
async def add_attachment(
    cert_id: str,
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form("other"),
    title: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """แนบหลักฐานตัวจริง — บันทึกลายนิ้วมือเสมอ เก็บตัวไฟล์เมื่อเปิดโหมดเก็บไฟล์"""
    data = await file.read()
    try:
        att = econtract_service.add_attachment(
            db, cert_id=cert_id, kind=kind, filename=file.filename or "file",
            data=data, content_type=file.content_type or "", note=note,
            uploaded_by=user.id, title=title,
        )
    except (ValueError, chain_service.ChainError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_attachment", resource_type="econtract",
        resource_id=cert_id,
        details=(f"แนบ {att['kind_th']} · {att['filename']} · SHA-256 {att['sha256'][:16]}… · "
                 f"{'เก็บตัวไฟล์' if att['stored'] else 'เก็บเฉพาะลายนิ้วมือ'}"),
    )
    db.commit()
    return att


@router.get("/{cert_id}/attachments/{att_id}/download")
async def download_attachment(
    cert_id: str,
    att_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ดาวน์โหลดหลักฐานตัวจริง (เฉพาะไฟล์ที่เก็บตัวไฟล์ไว้)"""
    try:
        path, name, mime = econtract_service.attachment_file(db, cert_id, att_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_attachment_download",
        resource_type="econtract", resource_id=cert_id, details=f"ดาวน์โหลดหลักฐาน {name}",
    )
    db.commit()
    return FileResponse(path, media_type=mime, filename=name)


@router.post("/{cert_id}/retention-storage")
async def set_retention_storage(
    cert_id: str,
    request: Request,
    store: str = Form("true"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """เปิด/ปิดการเก็บตัวไฟล์จริงของสัญญาฉบับนี้"""
    on = str(store).lower() in ("1", "true", "yes", "on")
    try:
        res = econtract_service.set_retention_storage(db, cert_id, on, changed_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_retention_storage",
        resource_type="econtract", resource_id=cert_id,
        details=f"{'เปิด' if on else 'ปิด'}การเก็บตัวไฟล์จริง",
    )
    db.commit()
    return res


@router.post("/{cert_id}/lock")
async def lock_original(
    cert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """ตรึงต้นฉบับ (ม.10) — หลังจากนี้ลงนามหรือประทับตราเพิ่มไม่ได้"""
    try:
        link = econtract_service.lock_original(db, cert_id=cert_id, locked_by=user.id)
    except (ValueError, chain_service.ChainError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_lock", resource_type="econtract",
        resource_id=cert_id, details=f"ตรึงต้นฉบับ {cert_id} · chain {link['chain_hash'][:16]}…",
    )
    db.commit()
    return link


@router.get("/{cert_id}/compliance")
async def compliance(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """รายงาน 7 เรื่อง — เอกสารนี้ทำอะไรไปแล้วบ้าง และยังค้างอะไร"""
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    return compliance_service.evaluate(db, cert)


@router.get("/{cert_id}/stamp-duty")
async def stamp_duty_info(
    cert_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ข้อมูลสำหรับยื่นขอเสียอากรแสตมป์ (อ.ส.9) — JSON"""
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    return compliance_service.stamp_duty_payload(db, cert)


@router.get("/{cert_id}/stamp-duty/download")
async def stamp_duty_download(
    cert_id: str,
    request: Request,
    format: str = "txt",
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER)),
):
    """ดาวน์โหลดใบข้อมูลสำหรับยื่น อ.ส.9 (txt = พิมพ์ได้, json = ป้อนเข้าระบบอื่น)"""
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="ไม่พบใบรับรอง")
    payload = compliance_service.stamp_duty_payload(db, cert)

    if format == "json":
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        media, ext = "application/json; charset=utf-8", "json"
    else:
        body = compliance_service.stamp_duty_worksheet_text(payload).encode("utf-8")
        media, ext = "text/plain; charset=utf-8", "txt"

    create_audit_log(
        db, request, user=user, action="econtract_stamp_duty_export",
        resource_type="econtract", resource_id=cert_id,
        details=f"ดาวน์โหลดข้อมูลยื่นอากรแสตมป์ (อ.ส.9) รูปแบบ {ext}",
    )
    db.commit()
    return Response(
        content=body, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{cert_id}_stamp_duty.{ext}"'},
    )


@router.post("/{cert_id}/steps/{step_key}")
async def record_step(
    cert_id: str,
    step_key: str,
    request: Request,
    actor: str = Form(""),
    ref: str = Form(""),
    note: str = Form(""),
    status: str = Form("done"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """บันทึกขั้นตอนที่เกิดนอกระบบ — e-Seal, e-Stamp Duty, Print out, e-Retention

    ขั้นตอนอื่น (e-Document / e-Signature / e-Original) ระบบตรวจจากข้อมูลจริงเอง
    บันทึกด้วยมือไม่ได้ เพื่อไม่ให้ใครกดผ่านทั้งที่ยังไม่ได้ทำ
    """
    try:
        rec = compliance_service.record_step(
            db, cert_id=cert_id, step_key=step_key, actor=actor.strip(),
            ref=ref.strip(), note=note, status=status, recorded_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    label = profile_service.STEP_META.get(step_key, {}).get("short_th", step_key)
    create_audit_log(
        db, request, user=user, action="econtract_step", resource_type="econtract",
        resource_id=cert_id,
        details=f"บันทึกขั้นตอน {label} ({status}) · {actor or '—'} · อ้างอิง {ref or '—'}",
    )
    db.commit()
    return rec


@router.get("/{cert_id}/evidence")
async def evidence_bundle(
    cert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Download a tamper-evident .zip evidence bundle (cert + signatures +
    audit trail + SHA-256 manifest)."""
    try:
        data = econtract_service.build_evidence_bundle(db, cert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    create_audit_log(
        db, request, user=user, action="econtract_evidence", resource_type="econtract",
        resource_id=cert_id, details=f"ส่งออกชุดหลักฐาน {cert_id}",
    )
    db.commit()
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{cert_id}_evidence.zip"'},
    )


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
