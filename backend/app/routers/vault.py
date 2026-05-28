from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, VaultKey, AuditLog
from app.schemas import VaultKeyCreate, VaultKeyResponse, VaultKeyDetailResponse
from app.middleware.auth import get_current_user, require_role, verify_password
from app.services.vault_service import vault_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/vault", tags=["Key Vault"])


@router.get("", response_model=list[VaultKeyResponse])
async def list_vault_keys(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    return db.query(VaultKey).order_by(VaultKey.created_at.desc()).all()


@router.get("/{key_id}", response_model=VaultKeyDetailResponse)
async def get_vault_key(
    key_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    vk = db.query(VaultKey).filter(VaultKey.id == key_id).first()
    if not vk:
        raise HTTPException(status_code=404, detail="Key not found")

    decrypted = vault_service.decrypt(vk.encrypted_value)
    masked = vault_service.mask_value(decrypted)

    return VaultKeyDetailResponse(
        id=vk.id,
        name=vk.name,
        provider=vk.provider,
        category=vk.category,
        description=vk.description,
        created_by=vk.created_by,
        created_at=vk.created_at,
        masked_value=masked,
    )


@router.post("/{key_id}/reveal")
async def reveal_vault_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Return the decrypted value for one-shot Copy-to-clipboard use.

    Audit-logged at WARNING — reveal events are the primary forensic
    signal for leaked-key investigations.
    """
    vk = db.query(VaultKey).filter(VaultKey.id == key_id).first()
    if not vk:
        raise HTTPException(status_code=404, detail="Key not found")

    decrypted = vault_service.decrypt(vk.encrypted_value)
    create_audit_log(
        db, request, user=user, action="reveal_key", resource_type="vault",
        resource_id=str(key_id),
        details=f"Revealed key for copy: {vk.name} ({vk.provider})",
        log_level="WARNING",
    )
    db.commit()
    return {"id": vk.id, "name": vk.name, "value": decrypted}


@router.post("", response_model=VaultKeyResponse)
async def create_vault_key(
    req: VaultKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    encrypted = vault_service.encrypt(req.value)

    vk = VaultKey(
        name=req.name,
        provider=req.provider,
        category=req.category,
        encrypted_value=encrypted,
        description=req.description,
        created_by=user.id,
    )
    db.add(vk)
    create_audit_log(
        db, request, user=user, action="create_key", resource_type="vault",
        resource_id=req.name, details=f"Added {req.provider} key: {req.name}",
    )
    db.commit()
    db.refresh(vk)
    return vk


@router.delete("/{key_id}")
async def delete_vault_key(
    key_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Delete a vault key. Requires admin's own password (re-auth)."""
    password = (payload or {}).get("password", "")
    if not password or not verify_password(password, user.password_hash):
        create_audit_log(
            db, request, user=user, action="delete_key_denied", resource_type="vault",
            resource_id=str(key_id),
            details="Vault delete denied — password re-authentication failed",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Password verification failed. Deleting a vault key requires re-authentication.",
        )

    vk = db.query(VaultKey).filter(VaultKey.id == key_id).first()
    if not vk:
        raise HTTPException(status_code=404, detail="Key not found")

    create_audit_log(
        db, request, user=user, action="delete_key", resource_type="vault",
        resource_id=str(key_id),
        details=f"Deleted key (re-authenticated): {vk.name} ({vk.provider})",
        log_level="WARNING",
    )
    db.delete(vk)
    db.commit()
    return {"message": "Key deleted"}
