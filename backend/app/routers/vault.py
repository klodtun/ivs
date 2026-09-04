from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, VaultKey, AuditLog, App, VaultGrant, VaultCapability
from app.schemas import VaultKeyCreate, VaultKeyResponse, VaultKeyDetailResponse
from app.middleware.auth import get_current_user, require_role, verify_password
from app.services.vault_service import vault_service
from app.services import vault_scope_service
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

    # บทบาทตอบว่าใครมีสิทธิ์ขอ ธงนี้ตอบว่าใบนี้ยอมให้ขอหรือไม่ กุญแจที่ตั้งเป็น
    # ใส่อย่างเดียวต้องไม่มีเส้นทางใดคืนค่าจริงออกไป แม้ผู้ขอเป็นผู้ดูแลระบบ
    if not vault_scope_service.may_reveal(vk):
        create_audit_log(
            db, request, user=user, action="reveal_key_denied", resource_type="vault",
            resource_id=str(key_id),
            details=f"ปฏิเสธการเปิดดูค่า: {vk.name} ({vk.provider}) ตั้งเป็นใส่อย่างเดียว",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="กุญแจใบนี้ตั้งไว้ให้ใส่เข้าคอนเทนเนอร์อย่างเดียว เปิดดูค่าไม่ได้",
        )

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
    env_override = (req.env_override or "").strip()[:120]
    if env_override and not vault_scope_service.env_name_valid(env_override):
        raise HTTPException(
            status_code=422,
            detail="ชื่อตัวแปรใช้ได้เฉพาะ A-Z a-z 0-9 และ _ และต้องไม่ขึ้นต้นด้วยตัวเลข",
        )

    encrypted = vault_service.encrypt(req.value)

    vk = VaultKey(
        name=req.name,
        provider=req.provider,
        category=req.category,
        encrypted_value=encrypted,
        description=req.description,
        env_override=env_override,
        namespace=(req.namespace or "").strip()[:120],
        allow_reveal=bool(req.allow_reveal),
        created_by=user.id,
    )
    db.add(vk)
    db.flush()
    create_audit_log(
        db, request, user=user, action="create_key", resource_type="vault",
        resource_id=req.name,
        details=(
            f"Added {req.provider} key: {req.name} "
            f"(ตัวแปร {vault_scope_service.env_name(vk)}"
            f"{', ใส่อย่างเดียว' if not vk.allow_reveal else ''})"
        ),
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


# ─────────────────────────────────────────────────────────────────────
# ขอบเขตของคลังกุญแจ — ตัวตน / กลุ่ม / ความสามารถ
# ─────────────────────────────────────────────────────────────────────

@router.get("/scope/overview")
async def vault_scope_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ภาพรวมสามแกน พร้อมส่วนต่างจากพฤติกรรมเดิม

    เฉพาะผู้ดูแลระบบ — รายการนี้บอกว่ากุญแจใบไหนอยู่ที่แอปใด ซึ่งเป็นแผนที่ที่
    คนที่จะขโมยกุญแจอยากได้มากที่สุด
    """
    out = vault_scope_service.overview(db)
    out["migration"] = vault_scope_service.diff_against_legacy(db)
    return out


@router.post("/{key_id}/grants")
async def grant_vault_key(
    key_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ให้สิทธิ์กุญแจใบนี้กับแอปหนึ่งตัว"""
    vk = db.query(VaultKey).filter(VaultKey.id == key_id).first()
    if not vk:
        raise HTTPException(status_code=404, detail="ไม่พบกุญแจ")
    app_row = db.query(App).filter(App.id == int(payload.get("app_id") or 0)).first()
    if not app_row:
        raise HTTPException(status_code=404, detail="ไม่พบแอป")

    try:
        cap = VaultCapability(payload.get("capability") or "inject")
    except ValueError:
        raise HTTPException(status_code=422, detail="ความสามารถไม่ถูกต้อง")
    if cap != VaultCapability.INJECT:
        # แอปทำได้อย่างเดียวคือรับค่าเข้า env ส่วน reveal และ rotate เป็นการ
        # กระทำของคน ให้กับแอปไม่ได้ ต่อให้ตั้งใจก็ไม่มีเส้นทางไหนใช้มัน
        raise HTTPException(
            status_code=422,
            detail="แอปรับได้เฉพาะสิทธิ์ inject — reveal และ rotate เป็นการกระทำของคน",
        )

    env_override = (payload.get("env_override") or "").strip()
    if env_override and not vault_scope_service.env_name_valid(env_override):
        raise HTTPException(
            status_code=422,
            detail="ชื่อตัวแปรต้องขึ้นต้นด้วยตัวอักษรหรือ _ และมีได้เฉพาะ A-Z a-z 0-9 _",
        )

    row = vault_scope_service.grant(db, vk, app_row, user,
                                    capability=cap,
                                    note=(payload.get("note") or "")[:2000],
                                    env_override=env_override)
    db.commit()
    create_audit_log(
        db, request, user=user, action="grant_vault_key", resource_type="vault",
        resource_id=str(key_id),
        details=(f"ให้สิทธิ์ {vault_scope_service.grant_env_name(vk, row)} "
                 f"แก่ {app_row.slug} ({cap.value})"),
        log_level="WARNING",
    )
    db.commit()
    return vault_scope_service.key_row(db, vk)


@router.post("/{key_id}/grants/by-namespace")
async def grant_by_namespace(
    key_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ให้สิทธิ์ทุกใบในกลุ่มที่ตรงรูปแบบ แก่แอปหนึ่งตัว

    `key_id` ไม่ถูกใช้ตัดสิน — เส้นทางนี้ทำงานระดับกลุ่ม แต่วางไว้ใต้กุญแจเพื่อให้
    สิทธิ์การเรียกเหมือนกัน รูปแบบถูกกางเป็นแถวจริงทันที ไม่เก็บไว้ตีความตอนรัน
    """
    app_row = db.query(App).filter(App.id == int(payload.get("app_id") or 0)).first()
    if not app_row:
        raise HTTPException(status_code=404, detail="ไม่พบแอป")
    pattern = (payload.get("namespace") or "").strip()
    if not pattern:
        raise HTTPException(status_code=422, detail="ต้องระบุกลุ่ม")

    matched = vault_scope_service.grant_by_namespace(db, pattern, app_row, user)
    db.commit()
    create_audit_log(
        db, request, user=user, action="grant_vault_namespace", resource_type="vault",
        resource_id=None,
        details=f"ให้สิทธิ์กลุ่ม {pattern} ({len(matched)} ใบ) แก่ {app_row.slug}",
        log_level="WARNING",
    )
    db.commit()
    return {"granted": len(matched), "keys": [vault_scope_service.env_name(k) for k in matched]}


@router.put("/grants/{grant_id}/env-name")
async def update_grant_env_name(
    grant_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """เปลี่ยนชื่อตัวแปรที่แอปตัวนี้จะได้รับกุญแจใบนี้

    ค่าว่างคือกลับไปใช้ชื่อของกุญแจ ไม่ใช่ลบสิทธิ์

    มีผลตอน deploy ครั้งถัดไปเท่านั้น คอนเทนเนอร์ที่รันอยู่ถือชื่อเดิมไว้ในโปรเซส
    เปลี่ยนชื่อแล้วไม่ redeploy = แอปยังอ่านชื่อเก่าต่อไปโดยไม่มีอะไรฟ้อง
    """
    row = db.query(VaultGrant).filter(VaultGrant.id == grant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบสิทธิ์")

    name = (payload.get("env_override") or "").strip()
    if name and not vault_scope_service.env_name_valid(name):
        raise HTTPException(
            status_code=422,
            detail="ชื่อตัวแปรต้องขึ้นต้นด้วยตัวอักษรหรือ _ และมีได้เฉพาะ A-Z a-z 0-9 _",
        )

    vk = db.query(VaultKey).filter(VaultKey.id == row.vault_key_id).first()
    app_row = db.query(App).filter(App.id == row.app_id).first()
    before = vault_scope_service.grant_env_name(vk, row) if vk else "?"

    vault_scope_service.set_grant_env_name(row, name)
    db.commit()

    after = vault_scope_service.grant_env_name(vk, row) if vk else "?"
    create_audit_log(
        db, request, user=user, action="update_vault_grant_env", resource_type="vault",
        resource_id=str(row.vault_key_id),
        details=(f"ชื่อตัวแปรของ {app_row.slug if app_row else '?'}: "
                 f"{before} → {after} — มีผลเมื่อ deploy ครั้งถัดไป"),
        log_level="WARNING",
    )
    db.commit()
    return vault_scope_service.key_row(db, vk) if vk else {"message": "แก้แล้ว"}


@router.delete("/grants/{grant_id}")
async def revoke_vault_grant(
    grant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ถอนสิทธิ์ — มีผลกับการ deploy ครั้งถัดไป ไม่ใช่กับคอนเทนเนอร์ที่รันอยู่

    ค่าที่ถูกใส่เข้า env ไปแล้วอยู่ในโปรเซสที่กำลังทำงาน การถอนสิทธิ์ไม่ดึงมันกลับ
    ถ้ากุญแจรั่วจริง ต้องเปลี่ยนค่ากุญแจ ไม่ใช่แค่ถอนสิทธิ์
    """
    row = db.query(VaultGrant).filter(VaultGrant.id == grant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="ไม่พบสิทธิ์")
    vk = db.query(VaultKey).filter(VaultKey.id == row.vault_key_id).first()
    app_row = db.query(App).filter(App.id == row.app_id).first()

    vault_scope_service.revoke(db, row, user)
    db.commit()
    create_audit_log(
        db, request, user=user, action="revoke_vault_key", resource_type="vault",
        resource_id=str(row.vault_key_id),
        details=(
            f"ถอนสิทธิ์ {vault_scope_service.env_name(vk) if vk else '?'} "
            f"จาก {app_row.slug if app_row else '?'} — มีผลเมื่อ deploy ครั้งถัดไป"
        ),
        log_level="WARNING",
    )
    db.commit()
    return {"message": "ถอนแล้ว", "takes_effect": "next_deploy"}


@router.put("/{key_id}/scope")
async def update_vault_key_scope(
    key_id: int,
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """ตั้งกลุ่มและความสามารถระดับใบ"""
    vk = db.query(VaultKey).filter(VaultKey.id == key_id).first()
    if not vk:
        raise HTTPException(status_code=404, detail="ไม่พบกุญแจ")

    changes = []
    if "env_override" in payload:
        raw = (payload.get("env_override") or "").strip()[:120]
        # ปฏิเสธชื่อที่ตั้งเป็นตัวแปรไม่ได้ตั้งแต่ตอนบันทึก แทนที่จะปล่อยให้ผ่าน
        # แล้วไปเงียบ ๆ อยู่ในคอนเทนเนอร์โดยไม่มีโปรแกรมไหนอ่านได้
        if raw and not vault_scope_service.env_name_valid(raw):
            raise HTTPException(
                status_code=422,
                detail="ชื่อตัวแปรใช้ได้เฉพาะ A-Z a-z 0-9 และ _ และต้องไม่ขึ้นต้นด้วยตัวเลข",
            )
        vk.env_override = raw
        changes.append(f"ชื่อตัวแปร={vault_scope_service.env_name(vk)}")
    if "namespace" in payload:
        vk.namespace = (payload.get("namespace") or "").strip()[:120]
        changes.append(f"กลุ่ม={vault_scope_service.namespace_of(vk)}")
    if "allow_reveal" in payload:
        vk.allow_reveal = bool(payload["allow_reveal"])
        changes.append(f"เปิดดูค่าได้={'ใช่' if vk.allow_reveal else 'ไม่'}")
    if "category" in payload:
        # หมวดตั้งได้ตอนสร้างเท่านั้นมาก่อน กุญแจที่จัดหมวดผิดจึงแก้ไม่ได้เลย
        # นอกจากลบทิ้งแล้วสร้างใหม่ ซึ่งแปลว่าต้องรู้ค่าความลับเดิม — เป็นเหตุผล
        # ที่ผิดในการบังคับให้คนเปิดดูค่ากุญแจ
        raw = (payload.get("category") or "").strip().lower()[:50]
        if raw not in ("general", "ai", "maps", "weather", "finance", "other"):
            raise HTTPException(status_code=422, detail="หมวดไม่ถูกต้อง")
        vk.category = raw
        changes.append(f"หมวด={raw}")
    db.commit()

    create_audit_log(
        db, request, user=user, action="update_vault_scope", resource_type="vault",
        resource_id=str(key_id),
        details=f"แก้ขอบเขต {vk.name}: {', '.join(changes) or 'ไม่มีการเปลี่ยนแปลง'}",
        log_level="WARNING",
    )
    db.commit()
    return vault_scope_service.key_row(db, vk)
