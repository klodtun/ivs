"""Exchange credentials — issue, list and revoke tokens for calling an app.

Issuing a token is not only a security act. It means this app's data will now
reach somebody else, which under PDPA makes that somebody a recipient of the
processing activity. So issuing records the recipient in the app's ROPA at the
same moment, rather than leaving the record to be updated by memory later.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from fastapi import Response
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import App, AppPdpa, ExchangeToken, TokenScope, User, UserRole
from app.services import exchange_gateway_service as gateway
from app.middleware.auth import require_role
from app.services import exchange_token_service as tokens
from app.services import ropa_service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/api/exchange", tags=["Exchange"])
logger = logging.getLogger(__name__)


@router.get("/tokens/{app_id}")
async def list_tokens(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Tokens issued for calling this app. Never includes the secret itself."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return {"app_id": app_id, "app_name": app.name, "tokens": tokens.list_for_app(db, app_id)}


@router.post("/tokens/{app_id}")
async def create_token(
    app_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Issue a token. The secret is in this response and nowhere else, ever.

    Body: {caller_name, scope, caller_kind?, allowed_paths?, ttl_hours?,
           rate_limit_per_hour?, label?}
    """
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    caller = (payload.get("caller_name") or "").strip()
    if not caller:
        raise HTTPException(status_code=422, detail="caller_name is required")
    try:
        scope = TokenScope(payload.get("scope") or "read")
    except ValueError:
        raise HTTPException(status_code=422, detail="scope must be read or write")

    ttl = payload.get("ttl_hours")
    ttl = int(ttl) if ttl not in (None, "", 0) else None

    try:
        row, plaintext = tokens.issue(
            db,
            target_app_id=app_id,
            caller_name=caller,
            scope=scope,
            caller_kind=payload.get("caller_kind") or "app",
            allowed_paths=payload.get("allowed_paths") or ["*"],
            ttl_hours=ttl,
            rate_limit_per_hour=int(payload.get("rate_limit_per_hour") or 1000),
            label=payload.get("label") or "",
            created_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # The activity has gained a recipient. Record it now, while we know it.
    record = db.query(AppPdpa).filter(AppPdpa.app_id == app_id).first()
    if not record:
        record = AppPdpa(app_id=app_id)
        db.add(record)
        db.flush()
    added, _ = ropa_service.add_recipient(
        db, record,
        kind=row.caller_kind,
        name=caller,
        purpose=payload.get("label") or f"เรียกใช้ข้อมูลผ่าน API ({scope.value})",
        note="บันทึกอัตโนมัติเมื่อออกโทเคนแลกเปลี่ยนข้อมูล",
    )

    create_audit_log(
        db, request, user=user, action="issue_exchange_token", resource_type="exchange",
        resource_id=str(app_id),
        details=(
            f"{app.name}: ออกโทเคน {row.token_prefix}… ให้ {caller} "
            f"สิทธิ์ {scope.value} หมดอายุ {row.expires_at or 'ไม่มีกำหนด'} "
            f"เพดาน {row.rate_limit_per_hour}/ชม."
            + ("  · เพิ่มผู้รับข้อมูลใน ROPA แล้ว" if added else "")
        ),
        log_level="WARNING",
    )
    db.commit()

    return {
        "token": plaintext,
        "warning": "โทเคนนี้แสดงเพียงครั้งเดียว คัดลอกเก็บไว้ก่อนปิดหน้าต่าง",
        "ropa_recipient_added": added,
        **tokens.to_dict(row, app.name),
    }


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Revoke a token. Takes effect on the next call, with no grace period."""
    row = db.query(ExchangeToken).filter(ExchangeToken.id == token_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    app = db.query(App).filter(App.id == row.target_app_id).first()

    tokens.revoke(db, token_id)
    create_audit_log(
        db, request, user=user, action="revoke_exchange_token", resource_type="exchange",
        resource_id=str(row.target_app_id),
        details=f"เพิกถอนโทเคน {row.token_prefix}… ของ {row.caller_name}",
        log_level="WARNING",
    )
    db.commit()
    return tokens.to_dict(row, app.name if app else "")


@router.post("/verify")
async def verify_token(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Check what a token would be allowed to do, without making the call.

    Body: {token, method, path}. Lets an integration be tested before it is
    wired up, and gives a refusal an explanation instead of a bare 403.
    """
    row, reason = tokens.verify(
        db,
        payload.get("token") or "",
        payload.get("method") or "GET",
        payload.get("path") or "/",
    )
    if not row:
        return {"allowed": False, "reason": reason}
    app = db.query(App).filter(App.id == row.target_app_id).first()
    return {
        "allowed": True,
        "reason": "",
        "caller_name": row.caller_name,
        "scope": row.scope.value,
        "target_app": app.name if app else "",
    }


# ── The gateway ──────────────────────────────────────────────────────
#
# One road in, so there is one place that checks the token, applies the field
# rules and writes the log. A second way in would make all three optional.


@router.api_route(
    "/call/{app_ref}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway_call(
    app_ref: str,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Call an app's API with an exchange token.

    Authenticate with `Authorization: Bearer <token>` or `X-IVS-Token`.
    Writes may send `Idempotency-Key`; a repeat of the same key returns the
    first result instead of doing the work twice.

    Note there is no iVS session here — the token *is* the credential, which is
    what lets another app or an AI call this without a browser login.
    """
    raw = request.headers.get("X-IVS-Token") or ""
    if not raw:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()

    method = request.method.upper()
    call_path = "/" + path.lstrip("/")

    token, reason = tokens.verify(db, raw, method, call_path)
    if not token:
        # 401 when there is no usable credential, 403 when there is one but it
        # does not cover this call — the caller needs to know which.
        code = 401 if reason in ("ไม่ได้ส่งโทเคน", "โทเคนไม่ถูกต้อง") else 403
        return JSONResponse(status_code=code, content={"detail": reason})

    app = db.query(App).filter(App.id == token.target_app_id).first()
    if not app:
        return JSONResponse(status_code=404, content={"detail": "ไม่พบแอปปลายทาง"})

    body = await request.body()
    idem_key = request.headers.get("Idempotency-Key") or ""

    # A write with no idempotency key is allowed but noted: the caller has
    # accepted that a retry will run the work twice.
    replay, conflict = gateway.check_idempotency(db, token, idem_key, method, call_path, body)
    if conflict:
        return JSONResponse(status_code=409, content={"detail": conflict})
    if replay:
        return JSONResponse(
            status_code=replay["status_code"],
            content=replay["body"],
            headers={"X-IVS-Idempotent-Replay": "true"},
        )

    status, payload, headers, err, raw = await gateway.forward(
        app, method, call_path, request.url.query,
        dict(request.headers), body, token.caller_name,
    )

    if err and err != "non-json":
        return JSONResponse(status_code=status, content={"detail": err})

    # Non-JSON bodies have no fields to filter; say so in the log rather than
    # pretending the rules ran.
    if err == "non-json":
        _audit_call(db, request, token, app, method, call_path, status,
                    "เนื้อหาไม่ใช่ JSON จึงไม่ได้กรองฟิลด์", idem_key)
        return Response(status_code=status, content=raw, headers=headers)

    filtered, applied = gateway.apply_field_rules(db, app.id, payload)

    if method in ("POST", "PUT", "PATCH", "DELETE") and idem_key and 200 <= status < 300:
        gateway.remember(db, token, idem_key, method, call_path, body, status, filtered)

    _audit_call(db, request, token, app, method, call_path, status,
                gateway.summarise(applied), idem_key)

    return JSONResponse(status_code=status, content=filtered)


def _audit_call(
    db: Session, request: Request, token: ExchangeToken, app: App,
    method: str, path: str, status: int, filtering: str, idem_key: str,
):
    """Record the call, including what was withheld.

    "What did this API actually disclose" is the question an audit has to be
    able to answer, so the entry carries the filtering result and not just the
    fact that a call happened.
    """
    try:
        create_audit_log(
            db, request, user=None, action="exchange_call", resource_type="exchange",
            resource_id=str(app.id),
            details=(
                f"{token.caller_name} → {app.name}: {method} {path} → {status} · "
                f"{filtering}"
                + (f" · Idempotency-Key {idem_key[:40]}" if idem_key else "")
            ),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"could not audit exchange call: {e}")
