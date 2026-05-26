from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, App, Tunnel, TunnelStatus, AuditLog
from app.schemas import TunnelCreate, TunnelResponse
from app.middleware.auth import get_current_user, require_role
from app.services.tunnel_service import tunnel_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/tunnels", tags=["Tunnels"])


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
    if req.duration_minutes not in allowed:
        raise HTTPException(status_code=400, detail=f"Duration must be one of: {allowed}")

    try:
        tunnel = await tunnel_service.create_tunnel(db, app, req.duration_minutes, user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    create_audit_log(
        db, request, user=user, action="create_tunnel", resource_type="tunnel",
        resource_id=str(tunnel.id),
        details=f"Tunnel for {app.name} ({req.duration_minutes}m) → {tunnel.public_url}",
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
