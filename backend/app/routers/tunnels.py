from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, App, Tunnel, TunnelStatus, AuditLog
from app.schemas import TunnelCreate, TunnelResponse
from app.middleware.auth import get_current_user, require_role
from app.services.tunnel_service import tunnel_service, get_tunnel_config, set_tunnel_config
from app.services.vault_service import vault_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/tunnels", tags=["Tunnels"])


class TunnelConfigResponse(BaseModel):
    provider: str
    ngrok_token_masked: str
    cloudflare_token_masked: str
    ngrok_configured: bool
    cloudflare_configured: bool


class TunnelConfigUpdate(BaseModel):
    provider: Optional[str] = None       # auto|ngrok|cloudflare|localtunnel
    ngrok_token: Optional[str] = None     # "" clears, None leaves unchanged
    cloudflare_token: Optional[str] = None


@router.get("/config", response_model=TunnelConfigResponse)
async def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    cfg = get_tunnel_config(db)
    return TunnelConfigResponse(
        provider=cfg["provider"],
        ngrok_token_masked=vault_service.mask_value(cfg["ngrok_token"]) if cfg["ngrok_token"] else "",
        cloudflare_token_masked=vault_service.mask_value(cfg["cf_token"]) if cfg["cf_token"] else "",
        ngrok_configured=bool(cfg["ngrok_token"]),
        cloudflare_configured=bool(cfg["cf_token"]),
    )


@router.put("/config")
async def update_config(
    req: TunnelConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    if req.provider is not None and req.provider not in ("auto", "ngrok", "cloudflare", "localtunnel"):
        raise HTTPException(status_code=422, detail="Invalid provider")
    set_tunnel_config(
        db,
        provider=req.provider,
        ngrok_token=req.ngrok_token,
        cf_token=req.cloudflare_token,
    )
    create_audit_log(
        db, request, user=user, action="update_tunnel_config", resource_type="system",
        details=f"Tunnel config updated (provider={req.provider or 'unchanged'})",
        log_level="WARNING",
    )
    db.commit()
    return {"message": "Tunnel config saved"}


@router.get("", response_model=list[TunnelResponse])
async def list_tunnels(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    return db.query(Tunnel).order_by(Tunnel.created_at.desc()).limit(50).all()


@router.post("", response_model=TunnelResponse)
async def create_tunnel(
    req: TunnelCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    app = db.query(App).filter(App.id == req.app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    allowed = [1, 10, 60, 180, 1440]
    # None = ไม่มีกำหนด — เป็นทางเลือกที่ตั้งใจ ไม่ใช่การเลี่ยงเพดานเวลา
    # จึงต้องมีเหตุผลกำกับเสมอ (บังคับที่ตัว service)
    if req.duration_minutes is not None and req.duration_minutes not in allowed:
        raise HTTPException(status_code=400, detail=f"Duration must be one of: {allowed}")

    try:
        tunnel = await tunnel_service.create_tunnel(
            db, app, req.duration_minutes, user.id,
            permanent_reason=req.permanent_reason or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    span = f"{req.duration_minutes}m" if req.duration_minutes else "ไม่มีกำหนด"
    create_audit_log(
        db, request, user=user, action="create_tunnel", resource_type="tunnel",
        resource_id=str(tunnel.id),
        details=(
            f"Tunnel for {app.name} ({span}) → {tunnel.public_url}"
            + (f" · เหตุผล: {req.permanent_reason}" if not req.duration_minutes else "")
        ),
        # อุโมงค์ที่เปิดค้างคือสิ่งที่ต้องหาเจอง่ายในบันทึกภายหลัง
        log_level="WARNING" if not req.duration_minutes else "INFO",
    )
    db.commit()

    return tunnel


@router.delete("/{tunnel_id}")
async def revoke_tunnel(
    tunnel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    tunnel = db.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
    if not tunnel:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    await tunnel_service.revoke_tunnel(db, tunnel)

    create_audit_log(
        db, request, user=user, action="revoke_tunnel", resource_type="tunnel",
        resource_id=str(tunnel_id), details="Tunnel revoked",
        log_level="WARNING",
    )
    db.commit()

    return {"message": "Tunnel revoked"}
