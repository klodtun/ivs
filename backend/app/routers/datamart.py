"""Data mart — configure outside sources, fetch them, read what came back.

The data is exposed read-only. Apps consume it through this API with an
exchange token, which means the same filtering and the same audit trail as any
other call, rather than each app reaching out to the outside world on its own.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DataMartRecord, DataMartSource, User, UserRole
from app.middleware.auth import require_role
from app.services import datamart_service as mart
from app.services import exchange_token_service as tokens
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/datamart", tags=["Data Mart"])
logger = logging.getLogger(__name__)


@router.get("/sources")
async def list_sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    rows = db.query(DataMartSource).order_by(DataMartSource.created_at.desc()).all()
    return {"sources": [mart.to_dict(db, s) for s in rows]}


@router.post("/sources")
async def create_source(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Register an outside source. The credential is a Vault key name, never the
    secret itself — one place holds secrets, and this is not it."""
    name = (payload.get("name") or "").strip()
    url = (payload.get("url") or "").strip()
    if not name or not url:
        raise HTTPException(status_code=422, detail="ต้องระบุชื่อและ URL")
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL ต้องขึ้นต้นด้วย http:// หรือ https://")

    row = DataMartSource(
        name=name[:200],
        description=(payload.get("description") or "")[:2000],
        url=url[:1000],
        method=(payload.get("method") or "GET").upper()[:10],
        vault_key_name=(payload.get("vault_key_name") or "")[:100],
        auth_header=(payload.get("auth_header") or "Authorization")[:100],
        fetch_interval_minutes=max(1, int(payload.get("fetch_interval_minutes") or 60)),
        retention_days=max(0, int(payload.get("retention_days") or 30)),
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    create_audit_log(
        db, request, user=user, action="datamart_add_source", resource_type="datamart",
        resource_id=str(row.id),
        details=(
            f"เพิ่มแหล่งข้อมูลภายนอก {name} · ดึงทุก {row.fetch_interval_minutes} นาที · "
            f"เก็บ {row.retention_days} วัน"
        ),
        log_level="WARNING",
    )
    db.commit()
    return mart.to_dict(db, row)


@router.post("/sources/{source_id}/fetch")
async def fetch_source(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Fetch now, without waiting for the interval."""
    row = db.query(DataMartSource).filter(DataMartSource.id == source_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบแหล่งข้อมูล")

    ok, msg = await mart.fetch_once(db, row)
    create_audit_log(
        db, request, user=user, action="datamart_fetch", resource_type="datamart",
        resource_id=str(source_id),
        details=f"ดึงข้อมูลจาก {row.name}: {'สำเร็จ' if ok else msg}",
    )
    db.commit()
    return mart.to_dict(db, row)


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    row = db.query(DataMartSource).filter(DataMartSource.id == source_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบแหล่งข้อมูล")
    name = row.name
    db.query(DataMartRecord).filter(DataMartRecord.source_id == source_id).delete()
    db.delete(row)
    create_audit_log(
        db, request, user=user, action="datamart_delete_source", resource_type="datamart",
        resource_id=str(source_id), details=f"ลบแหล่งข้อมูล {name} พร้อมข้อมูลที่เก็บไว้",
        log_level="WARNING",
    )
    db.commit()
    return {"deleted": True}


@router.get("/sources/{source_id}/latest")
async def latest_for_ui(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    data = mart.latest(db, source_id)
    if data is None:
        raise HTTPException(status_code=404, detail="ยังไม่มีข้อมูลที่ดึงมา")
    return data


@router.get("/data/{source_id}")
async def data_for_apps(
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Read a source with an exchange token — this is how apps consume it.

    Deliberately the same credential as the gateway: an app reading shared data
    is doing the same kind of thing as an app reading another app, and should
    not get a second, looser way to do it.
    """
    raw = request.headers.get("X-IVS-Token") or ""
    if not raw:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()

    token, reason = tokens.verify(db, raw, "GET", f"/datamart/{source_id}")
    if not token:
        raise HTTPException(status_code=401 if not raw else 403, detail=reason)

    data = mart.latest(db, source_id)
    if data is None:
        raise HTTPException(status_code=404, detail="ยังไม่มีข้อมูลที่ดึงมา")

    source = db.query(DataMartSource).filter(DataMartSource.id == source_id).first()
    create_audit_log(
        db, request, user=None, action="datamart_read", resource_type="datamart",
        resource_id=str(source_id),
        details=f"{token.caller_name} อ่านข้อมูลกองกลาง {source.name if source else source_id}",
    )
    db.commit()
    return data
