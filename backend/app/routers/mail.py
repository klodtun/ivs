"""
Mail Router — ตั้งค่าตัวรีเลย์ ส่งทดสอบ ดูคิว และทะเบียน ROPA ของระบบจดหมาย

ทุกเส้นทางเป็นของผู้ดูแลระบบเท่านั้น การตั้งค่าจดหมายกำหนดว่าข้อมูลของผู้ใช้จะ
ออกจากเครื่องไปที่ไหน จึงเป็นเรื่องของผู้ควบคุมข้อมูล ไม่ใช่ของผู้พัฒนาแอป
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models import MailOutbox, User, UserRole
from app.services import mail_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/mail", tags=["mail"])


class MailConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    preset: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    security: Optional[str] = None
    username: Optional[str] = None
    # None = ไม่เปลี่ยน · "" = ล้างรหัสผ่าน
    password: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    locale: Optional[str] = None
    recipients: Optional[str] = None
    dashboard_url: Optional[str] = None


class MailTestRequest(BaseModel):
    to: str


class RopaConfirmRequest(BaseModel):
    legal_basis: str
    dpa_url: str = ""
    dpa_note: str = ""
    purpose: Optional[str] = None
    retention: Optional[str] = None


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    return mail_service.public_config(db)


@router.put("/config")
async def update_config(
    req: MailConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    try:
        cfg = mail_service.set_config(db, **req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    changed = [k for k, v in req.model_dump().items() if v is not None and k != "password"]
    if req.password is not None:
        changed.append("password:" + ("set" if req.password else "cleared"))
    create_audit_log(
        db, request, user=user, action="update_mail_config", resource_type="mail",
        details=f"Mail relay config updated: {', '.join(changed) or 'no fields'} "
                f"(host={cfg['host'] or '-'}, enabled={cfg['enabled']})",
    )
    db.commit()
    return cfg


@router.post("/test")
async def send_test(
    req: MailTestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ส่งทันทีและคืนข้อความจริงจากเซิร์ฟเวอร์ปลายทาง — ไม่ผ่านคิว เพราะผู้ดูแลกำลังรอดูผล"""
    return mail_service.send_test(db, req.to.strip(), user)


@router.get("/status")
async def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    return mail_service.status(db)


@router.get("/outbox")
async def list_outbox(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    return mail_service.outbox_rows(db, limit=max(1, min(limit, 200)))


@router.post("/outbox/{row_id}/retry")
async def retry_outbox(
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    row = db.query(MailOutbox).filter(MailOutbox.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mail not found")
    if row.status not in ("failed", "dead"):
        raise HTTPException(status_code=409, detail=f"Mail is {row.status}; only failed or dead mail can be retried")
    mail_service.requeue(db, row)
    create_audit_log(
        db, request, user=user, action="mail.retry", resource_type="mail",
        resource_id=str(row.id), details=f"Requeued mail to {row.to_email} ({row.template})",
    )
    db.commit()
    return {"message": "requeued", "id": row.id}


@router.post("/process-now")
async def process_now(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ให้ผู้ดูแลเร่งคิวได้ทันทีโดยไม่ต้องรอรอบ 30 วินาที"""
    return mail_service.process_queue(db)


@router.get("/ropa")
async def get_ropa(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    from app.services.ropa_service import basis_options
    return {"record": mail_service.ensure_ropa(db), "basis_options": basis_options()}


@router.put("/ropa/confirm")
async def confirm_ropa(
    req: RopaConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    try:
        record = mail_service.confirm_ropa(
            db, user, legal_basis=req.legal_basis, dpa_url=req.dpa_url,
            dpa_note=req.dpa_note, purpose=req.purpose, retention=req.retention,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    create_audit_log(
        db, request, user=user, action="confirm_mail_ropa", resource_type="pdpa",
        details=f"Mail notification ROPA confirmed: basis={req.legal_basis}, dpa={'yes' if req.dpa_url else 'no'}",
    )
    db.commit()
    return record
