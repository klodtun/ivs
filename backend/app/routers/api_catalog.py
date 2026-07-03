"""
API Catalog Router — managed catalog of deployed-app APIs.

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models import ApiCatalogEntry, ApiCatalogVersion, User, UserRole
from app.services import api_catalog_service as svc
from app.services.audit_service import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catalog", tags=["api-catalog"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class CatalogEntryCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: str
    base_url: str
    method: str = "GET"
    path: str = "/"
    api_key: Optional[str] = None
    api_schema: Optional[str] = None
    description: Optional[str] = ""
    category: str = "external"
    app_id: Optional[int] = None


class CatalogEntryReplace(BaseModel):
    model_config = {"protected_namespaces": ()}
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_schema: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    reason: str = ""


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@router.get("")
async def list_entries(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """List all catalog entries (API keys masked)."""
    entries = db.query(ApiCatalogEntry).order_by(ApiCatalogEntry.created_at.desc()).all()
    return [svc.to_safe_dict(e) for e in entries]


@router.get("/{entry_id}")
async def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return svc.to_safe_dict(entry)


@router.post("", status_code=201)
async def create_entry(
    body: CatalogEntryCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Manually add a catalog entry (e.g. for external/3rd-party APIs)."""
    from app.services.api_catalog_service import _encrypt
    entry = ApiCatalogEntry(
        app_id=body.app_id,
        name=body.name,
        method=body.method.upper(),
        path=body.path or "/",
        encrypted_base_url=_encrypt(body.base_url),
        encrypted_api_key=_encrypt(body.api_key) if body.api_key else None,
        encrypted_schema=_encrypt(body.api_schema) if body.api_schema else None,
        description=body.description or "",
        category=body.category or "external",
        current_version=1,
        discovery_source="manual",
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    create_audit_log(
        db, request, user,
        action="create_catalog_entry", resource_type="api_catalog",
        resource_id=str(entry.id),
        details=f"Created catalog entry '{body.name}'",
    )
    return svc.to_safe_dict(entry)


@router.post("/scan")
async def scan_apps(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Trigger auto-discovery scan across all running apps."""
    summary = svc.scan_all_apps(db)
    create_audit_log(
        db, request, user,
        action="scan_catalog", resource_type="api_catalog",
        details=f"Scanned {summary['scanned']} apps — {summary['new']} new, {summary['updated']} updated, {summary['failed']} failed",
    )
    return summary


@router.post("/{entry_id}/test")
async def test_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Call the API endpoint and return status + diagnostic info."""
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return svc.test_entry(db, entry)


@router.put("/{entry_id}")
async def replace_entry(
    entry_id: int,
    body: CatalogEntryReplace,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Replace an entry's config. Old config goes into history for restore."""
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    snapshot = svc.replace_entry(
        db, entry,
        new_base_url=body.base_url,
        new_api_key=body.api_key,
        new_schema=body.api_schema,
        new_method=body.method,
        new_path=body.path,
        user_id=user.id,
        reason=body.reason or "",
    )
    create_audit_log(
        db, request, user,
        action="replace_catalog_entry", resource_type="api_catalog",
        resource_id=str(entry.id),
        details=f"Replaced entry '{entry.name}' — snapshot v{snapshot.version_number} saved. Reason: {body.reason}",
        log_level="WARNING",
    )
    return svc.to_safe_dict(entry)


@router.get("/{entry_id}/history")
async def get_history(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """List prior versions of this entry."""
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    return [svc.version_to_dict(v) for v in entry.versions]


@router.post("/{entry_id}/restore/{version_id}")
async def restore_version(
    entry_id: int,
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Restore an entry to a prior version (current config saved to history)."""
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    version = db.query(ApiCatalogVersion).filter_by(id=version_id, catalog_id=entry_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    svc.restore_version(db, entry, version, user_id=user.id)
    create_audit_log(
        db, request, user,
        action="restore_catalog_entry", resource_type="api_catalog",
        resource_id=str(entry.id),
        details=f"Restored entry '{entry.name}' to v{version.version_number}",
        log_level="WARNING",
    )
    return svc.to_safe_dict(entry)


@router.post("/{entry_id}/reveal-key")
async def reveal_key(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """One-shot decrypt of the API key for clipboard copy. Always audit-logged."""
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    if not entry.encrypted_api_key:
        raise HTTPException(status_code=404, detail="No API key stored on this entry")

    create_audit_log(
        db, request, user,
        action="reveal_catalog_key", resource_type="api_catalog",
        resource_id=str(entry.id),
        details=f"Revealed API key for entry '{entry.name}'",
        log_level="WARNING",
    )
    return svc.to_safe_dict(entry, include_key=True)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    entry = db.query(ApiCatalogEntry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    name = entry.name
    db.delete(entry)
    db.commit()
    create_audit_log(
        db, request, user,
        action="delete_catalog_entry", resource_type="api_catalog",
        details=f"Deleted catalog entry '{name}'",
        log_level="WARNING",
    )
