from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, AuditLog, UserAppAccess, App, Tunnel, VaultKey, AppPdpa, AuditLogExport
from app.schemas import (
    LoginRequest, Token, UserCreate, UserResponse, UserUpdate,
    UserAppAccessSet, UserAppAccessResponse,
)
from app.middleware.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role,
)
from app.services.audit_service import create_audit_log


def _enrich_user_response(user: User, db: Session) -> dict:
    """Add allowed_app_ids and access_all_apps to user data."""
    access_records = db.query(UserAppAccess).filter(UserAppAccess.user_id == user.id).all()
    access_all = any(r.access_all for r in access_records)
    app_ids = [r.app_id for r in access_records if r.app_id is not None]
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "allowed_app_ids": app_ids,
        "access_all_apps": access_all,
    }

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

DEFAULT_ADMIN_USERNAME = "admin"


@router.get("/default-admin-exists")
async def default_admin_exists(db: Session = Depends(get_db)):
    """Public endpoint — login page shows the default credentials hint
    only while the seeded admin/admin123 account is still present."""
    exists = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first() is not None
    return {"exists": exists}


@router.get("/admin-count")
async def admin_count(db: Session = Depends(get_db)):
    """Public — login page uses this to decide whether to show the
    last-admin recovery button. Returns count of active admins."""
    count = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active == True)
        .count()
    )
    return {"count": count}


@router.post("/factory-reset-last-admin")
async def factory_reset_last_admin(
    request: Request,
    db: Session = Depends(get_db),
):
    """Wipe the last active admin and restore the default admin/admin123.

    Public endpoint (no auth — operator forgot password). Only succeeds
    when exactly ONE active admin exists, so a working multi-admin
    deployment cannot be reset by a passerby.

    Audit-logged at CRITICAL.
    """
    from app.middleware.auth import hash_password
    from app.models import App, Tunnel, VaultKey, UserAppAccess, AppPdpa, AuditLogExport

    admins = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active == True)
        .all()
    )
    if len(admins) != 1:
        raise HTTPException(
            status_code=400,
            detail="Factory reset only available when exactly one active admin exists.",
        )

    target = admins[0]
    target_username = target.username
    target_id = target.id

    # Reassign owned records — orphans would otherwise break FK or hide
    # apps from any future admin. We move everything to the NEW default
    # admin we're about to create.
    new_admin = User(
        username=DEFAULT_ADMIN_USERNAME,
        email=f"{DEFAULT_ADMIN_USERNAME}@ivs.local",
        password_hash=hash_password("admin123"),
        role=UserRole.ADMIN,
    )
    # If the existing admin already has the default username, just reset
    # its password and skip the reassignment dance.
    if target.username == DEFAULT_ADMIN_USERNAME:
        target.password_hash = hash_password("admin123")
        create_audit_log(
            db, request, user=None, action="factory_reset_password",
            resource_type="auth", resource_id=str(target.id),
            details=f"Reset password of '{target_username}' to default (factory reset)",
            log_level="CRITICAL",
        )
        db.commit()
        return {"reset": "password_only", "username": DEFAULT_ADMIN_USERNAME}

    # Different username — create fresh default, reassign, then delete old
    db.add(new_admin)
    db.flush()  # get new_admin.id without committing yet

    db.query(App).filter(App.owner_id == target_id).update(
        {"owner_id": new_admin.id}, synchronize_session=False
    )
    db.query(Tunnel).filter(Tunnel.created_by == target_id).update(
        {"created_by": new_admin.id}, synchronize_session=False
    )
    db.query(VaultKey).filter(VaultKey.created_by == target_id).update(
        {"created_by": new_admin.id}, synchronize_session=False
    )
    db.query(AppPdpa).filter(AppPdpa.updated_by == target_id).update(
        {"updated_by": new_admin.id}, synchronize_session=False
    )
    db.query(AuditLogExport).filter(AuditLogExport.exported_by == target_id).update(
        {"exported_by": new_admin.id}, synchronize_session=False
    )
    db.query(UserAppAccess).filter(UserAppAccess.user_id == target_id).delete(
        synchronize_session=False
    )
    db.delete(target)

    create_audit_log(
        db, request, user=None, action="factory_reset_admin",
        resource_type="auth", resource_id=str(target_id),
        details=(
            f"Factory-reset triggered: deleted last admin '{target_username}' "
            f"and restored default admin/admin123 (new uid {new_admin.id})"
        ),
        log_level="CRITICAL",
    )
    db.commit()
    return {"reset": "replaced", "username": DEFAULT_ADMIN_USERNAME, "previous": target_username}


@router.post("/login", response_model=Token)
async def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        # Log failed login attempt — WARNING level
        create_audit_log(
            db, request, user=None, action="login_failed", resource_type="auth",
            details=f"Failed login attempt for username: {req.username}",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        create_audit_log(
            db, request, user=user, action="login_disabled", resource_type="auth",
            details=f"Login attempt on disabled account: {user.username}",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    token = create_access_token(data={"sub": user.username, "role": user.role.value if hasattr(user.role, 'value') else user.role})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 480,
    )

    create_audit_log(
        db, request, user=user, action="login", resource_type="auth",
        details=f"User {user.username} logged in successfully",
    )
    db.commit()

    return Token(access_token=token)


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    create_audit_log(
        db, request, user=user, action="logout", resource_type="auth",
        details=f"User {user.username} logged out",
    )
    db.commit()
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _enrich_user_response(user, db)


@router.post("/users", response_model=UserResponse)
async def create_user(
    req: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    if db.query(User).filter((User.username == req.username) | (User.email == req.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    create_audit_log(
        db, request, user=admin, action="create_user", resource_type="user",
        resource_id=req.username, details=f"Created user {req.username} with role {req.role}",
    )
    db.commit()
    db.refresh(user)
    return _enrich_user_response(user, db)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    users = db.query(User).all()
    return [_enrich_user_response(u, db) for u in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    req: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes = []
    if req.email is not None:
        changes.append(f"email: {user.email} -> {req.email}")
        user.email = req.email
    if req.role is not None:
        old_role = user.role.value if hasattr(user.role, "value") else user.role
        changes.append(f"role: {old_role} -> {req.role}")
        user.role = req.role
    if req.is_active is not None:
        changes.append(f"active: {user.is_active} -> {req.is_active}")
        user.is_active = req.is_active

    log_level = "WARNING" if req.role is not None or req.is_active is not None else "INFO"
    create_audit_log(
        db, request, user=admin, action="update_user", resource_type="user",
        resource_id=str(user_id),
        details=f"Updated user {user.username}: {', '.join(changes)}",
        log_level=log_level,
    )
    db.commit()
    db.refresh(user)
    return _enrich_user_response(user, db)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    password = (payload or {}).get("password", "")
    if not password or not verify_password(password, admin.password_hash):
        create_audit_log(
            db, request, user=admin, action="delete_user_denied",
            resource_type="user", resource_id=str(user_id),
            details="Delete attempt denied — password re-authentication failed",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Password verification failed. Deleting a user requires re-authentication.",
        )

    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.role == UserRole.ADMIN:
        other_admins = (
            db.query(User)
            .filter(User.role == UserRole.ADMIN, User.id != user_id, User.is_active == True)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last active admin.",
            )

    # Extra protection for the seeded default admin: only let it be deleted
    # once a NON-default admin (different username) exists. This prevents
    # an operator from locking themselves out before they've replaced the
    # well-known credentials with their own account.
    if target.username == DEFAULT_ADMIN_USERNAME:
        alternative_admin = (
            db.query(User)
            .filter(
                User.role == UserRole.ADMIN,
                User.username != DEFAULT_ADMIN_USERNAME,
                User.is_active == True,
            )
            .first()
        )
        if alternative_admin is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Create another Admin account (with a different username) "
                    "before deleting the default 'admin' account."
                ),
            )

    reassigned_apps = (
        db.query(App).filter(App.owner_id == user_id).update(
            {"owner_id": admin.id}, synchronize_session=False
        )
    )
    db.query(Tunnel).filter(Tunnel.created_by == user_id).update(
        {"created_by": admin.id}, synchronize_session=False
    )
    db.query(VaultKey).filter(VaultKey.created_by == user_id).update(
        {"created_by": admin.id}, synchronize_session=False
    )
    db.query(AuditLogExport).filter(AuditLogExport.exported_by == user_id).update(
        {"exported_by": admin.id}, synchronize_session=False
    )
    db.query(AppPdpa).filter(AppPdpa.updated_by == user_id).update(
        {"updated_by": admin.id}, synchronize_session=False
    )
    db.query(UserAppAccess).filter(UserAppAccess.user_id == user_id).delete(
        synchronize_session=False
    )

    target_username = target.username
    db.delete(target)
    create_audit_log(
        db, request, user=admin, action="delete_user", resource_type="user",
        resource_id=str(user_id),
        details=f"Deleted user {target_username}; reassigned {reassigned_apps} app(s) to {admin.username}",
        log_level="WARNING",
    )
    db.commit()
    return {
        "message": f"User {target_username} deleted",
        "reassigned_apps": reassigned_apps,
        "new_owner": admin.username,
    }


@router.post("/users/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Disable a user account.

    Disabling locks the user out completely; while the existing /users/{id}
    PUT endpoint will accept is_active=false too, this dedicated path adds
    two safety nets that misclicks on the UI shouldn't bypass:

      1. The calling admin must re-enter their OWN password (proof that
         the active session belongs to the person clicking, not someone
         walking past an unlocked laptop).
      2. You cannot disable yourself — too easy to lock everyone out of
         an IVS install whose only admin clicks the wrong row.

    Re-enabling (is_active=true) goes through the regular update_user
    endpoint without the password challenge — restoring access is the
    safer direction.
    """
    password = (payload or {}).get("password", "")
    if not password or not verify_password(password, admin.password_hash):
        create_audit_log(
            db, request, user=admin, action="disable_user_denied",
            resource_type="user", resource_id=str(user_id),
            details="Disable attempt denied — password re-authentication failed",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Password verification failed. Disabling a user requires re-authentication.",
        )

    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot disable your own account.",
        )

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not target.is_active:
        # Idempotent: already disabled. Don't error — just return current state.
        return _enrich_user_response(target, db)

    target.is_active = False
    create_audit_log(
        db, request, user=admin, action="disable_user", resource_type="user",
        resource_id=str(user_id),
        details=f"Disabled user {target.username} (re-authenticated)",
        log_level="WARNING",
    )
    db.commit()
    db.refresh(target)
    return _enrich_user_response(target, db)


@router.get("/users/{user_id}/access", response_model=UserAppAccessResponse)
async def get_user_app_access(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access_records = db.query(UserAppAccess).filter(UserAppAccess.user_id == user_id).all()
    access_all = any(r.access_all for r in access_records)
    app_ids = [r.app_id for r in access_records if r.app_id is not None]
    return UserAppAccessResponse(user_id=user_id, app_ids=app_ids, access_all=access_all)


@router.put("/users/{user_id}/access", response_model=UserAppAccessResponse)
async def set_user_app_access(
    user_id: int,
    req: UserAppAccessSet,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Clear existing access
    db.query(UserAppAccess).filter(UserAppAccess.user_id == user_id).delete()

    if req.access_all:
        db.add(UserAppAccess(user_id=user_id, app_id=None, access_all=True))
    else:
        for app_id in req.app_ids:
            db.add(UserAppAccess(user_id=user_id, app_id=app_id, access_all=False))

    create_audit_log(
        db, request, user=admin, action="set_access", resource_type="user",
        resource_id=str(user_id),
        details=f"Set app access for {user.username}: {'ALL' if req.access_all else f'{len(req.app_ids)} apps'}",
        log_level="WARNING",
    )
    db.commit()

    return UserAppAccessResponse(user_id=user_id, app_ids=req.app_ids, access_all=req.access_all)
