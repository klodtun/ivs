from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, AuditLog, UserAppAccess
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
