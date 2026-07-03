"""
API Catalog Service — auto-discover, encrypt, test, replace, restore.

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

Responsibilities:
  - scan_all_apps()        — fetch /openapi.json from each running app, upsert entries
  - test_entry()           — perform an HTTP call to verify the endpoint is alive
  - replace_entry()        — update URL/key/schema, snapshot old config to history
  - restore_version()      — revert an entry to a prior version

All sensitive fields (base_url, api_key, schema) are encrypted at rest with
the Fernet key derived from settings.VAULT_KEY (same scheme as VaultService).
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List

import httpx
from sqlalchemy.orm import Session

from app.models import App, AppStatus, ApiCatalogEntry, ApiCatalogVersion
from app.services.vault_service import vault_service

logger = logging.getLogger(__name__)

# Cap stored schema at 200KB to avoid bloat from huge OpenAPI specs
SCHEMA_MAX_BYTES = 200_000

# How long to wait for /openapi.json fetch and test calls
HTTP_TIMEOUT = 5.0


def _utcnow():
    return datetime.now(timezone.utc)


def _encrypt(text: Optional[str]) -> Optional[str]:
    if text is None or text == "":
        return None
    return vault_service.encrypt(text)


def _decrypt(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return vault_service.decrypt(ciphertext)
    except Exception as e:
        logger.warning(f"api_catalog decrypt failed: {e}")
        return None


def _app_base_url(app: App) -> Optional[str]:
    """Build the in-network URL to reach the app's API root."""
    if not app.port:
        return None
    # On macOS dev: host.docker.internal works inside containers; for direct
    # calls from the backend container, use the container name.
    # Simplest cross-platform: use the host port mapping.
    return f"http://localhost:{app.port}"


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

def _try_fetch_openapi(base_url: str) -> Optional[Dict]:
    """Fetch /openapi.json (FastAPI default) or /api-docs (other frameworks)."""
    for candidate in ("/openapi.json", "/api/openapi.json", "/docs/openapi.json", "/api-docs"):
        url = base_url.rstrip("/") + candidate
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                r = client.get(url)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def scan_all_apps(db: Session) -> Dict:
    """
    Walk every RUNNING app and discover its API root. Insert new catalog
    entries for apps not yet cataloged; refresh schema for existing ones.

    Returns a summary dict: {scanned, new, updated, failed}.
    """
    summary = {"scanned": 0, "new": 0, "updated": 0, "failed": 0, "details": []}

    running_apps = db.query(App).filter(App.status == AppStatus.RUNNING).all()
    for app in running_apps:
        summary["scanned"] += 1
        base_url = _app_base_url(app)
        if not base_url:
            summary["failed"] += 1
            summary["details"].append({"slug": app.slug, "status": "NO_PORT"})
            continue

        openapi = _try_fetch_openapi(base_url)
        # Truncate schema if too big
        schema_str = None
        if openapi:
            try:
                schema_str = json.dumps(openapi)
                if len(schema_str) > SCHEMA_MAX_BYTES:
                    # Keep only paths summary
                    minimal = {
                        "openapi": openapi.get("openapi"),
                        "info": openapi.get("info"),
                        "paths": {k: list(v.keys()) for k, v in (openapi.get("paths") or {}).items()},
                    }
                    schema_str = json.dumps(minimal)
            except Exception:
                schema_str = None

        # Upsert one entry per app — the API "root" entry
        existing = db.query(ApiCatalogEntry).filter_by(
            app_id=app.id, path="/", discovery_source="auto"
        ).first()

        if existing:
            existing.encrypted_base_url = _encrypt(base_url)
            if schema_str:
                existing.encrypted_schema = _encrypt(schema_str)
            existing.updated_at = _utcnow()
            summary["updated"] += 1
            summary["details"].append({"slug": app.slug, "status": "UPDATED"})
        else:
            entry = ApiCatalogEntry(
                app_id=app.id,
                name=app.name,
                method="GET",
                path="/",
                encrypted_base_url=_encrypt(base_url),
                encrypted_schema=_encrypt(schema_str) if schema_str else None,
                description=app.description or f"Auto-discovered API for {app.name}",
                category="app",
                current_version=1,
                discovery_source="auto",
                is_active=True,
            )
            db.add(entry)
            summary["new"] += 1
            summary["details"].append({"slug": app.slug, "status": "NEW"})

    db.commit()
    return summary


# --------------------------------------------------------------------------- #
# Test
# --------------------------------------------------------------------------- #

def test_entry(db: Session, entry: ApiCatalogEntry) -> Dict:
    """
    Call the API endpoint and record the result on the entry.

    Returns: {status, http_code, latency_ms, message, body_snippet}
    """
    base_url = _decrypt(entry.encrypted_base_url) or ""
    api_key = _decrypt(entry.encrypted_api_key) or ""
    url = base_url.rstrip("/") + (entry.path or "/")

    headers = {}
    if api_key:
        # Convention: if key looks like JWT/Bearer use Authorization; else X-API-Key
        if api_key.count(".") == 2 and len(api_key) > 40:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["X-API-Key"] = api_key

    method = (entry.method or "GET").upper()
    start = time.monotonic()
    result = {"status": "FAIL", "http_code": None, "latency_ms": 0, "message": "", "body_snippet": ""}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            r = client.request(method, url, headers=headers)
        elapsed = int((time.monotonic() - start) * 1000)
        result["http_code"] = r.status_code
        result["latency_ms"] = elapsed
        body = (r.text or "")[:500]
        result["body_snippet"] = body
        if 200 <= r.status_code < 400:
            result["status"] = "OK"
            result["message"] = f"HTTP {r.status_code} in {elapsed} ms"
        else:
            result["message"] = f"HTTP {r.status_code} — endpoint returned error"
    except httpx.TimeoutException:
        result["message"] = f"Timeout after {HTTP_TIMEOUT:.1f}s"
        result["latency_ms"] = int((time.monotonic() - start) * 1000)
    except httpx.ConnectError as e:
        result["message"] = f"Connection refused / DNS failure: {e}"
    except Exception as e:
        result["message"] = f"Error: {e}"

    entry.last_test_at = _utcnow()
    entry.last_test_status = result["status"]
    entry.last_test_message = result["message"]
    entry.last_test_http_code = result["http_code"]
    entry.last_test_latency_ms = result["latency_ms"]
    db.commit()
    return result


# --------------------------------------------------------------------------- #
# Replace / Restore
# --------------------------------------------------------------------------- #

def replace_entry(
    db: Session,
    entry: ApiCatalogEntry,
    new_base_url: Optional[str] = None,
    new_api_key: Optional[str] = None,
    new_schema: Optional[str] = None,
    new_method: Optional[str] = None,
    new_path: Optional[str] = None,
    user_id: Optional[int] = None,
    reason: str = "",
) -> ApiCatalogVersion:
    """
    Snapshot the current entry config into ApiCatalogVersion, then apply
    the new values. Any param left as None keeps the existing value.
    """
    # Snapshot prior
    snapshot = ApiCatalogVersion(
        catalog_id=entry.id,
        version_number=entry.current_version,
        encrypted_base_url=entry.encrypted_base_url,
        encrypted_api_key=entry.encrypted_api_key,
        encrypted_schema=entry.encrypted_schema,
        method=entry.method,
        path=entry.path,
        replaced_by_id=user_id,
        reason=reason,
    )
    db.add(snapshot)

    # Apply new
    if new_base_url is not None:
        entry.encrypted_base_url = _encrypt(new_base_url)
    if new_api_key is not None:
        entry.encrypted_api_key = _encrypt(new_api_key) if new_api_key else None
    if new_schema is not None:
        entry.encrypted_schema = _encrypt(new_schema) if new_schema else None
    if new_method is not None:
        entry.method = new_method.upper()
    if new_path is not None:
        entry.path = new_path

    entry.current_version = (entry.current_version or 1) + 1
    entry.updated_at = _utcnow()
    db.commit()
    db.refresh(snapshot)
    return snapshot


def restore_version(
    db: Session,
    entry: ApiCatalogEntry,
    version: ApiCatalogVersion,
    user_id: Optional[int] = None,
) -> ApiCatalogVersion:
    """
    Restore an entry to a prior version. The current config is snapshotted
    to history first (so the restore itself is also reversible).
    """
    return replace_entry(
        db, entry,
        new_base_url=_decrypt(version.encrypted_base_url),
        new_api_key=_decrypt(version.encrypted_api_key) or "",
        new_schema=_decrypt(version.encrypted_schema) or "",
        new_method=version.method,
        new_path=version.path,
        user_id=user_id,
        reason=f"Restored from version {version.version_number}",
    )


# --------------------------------------------------------------------------- #
# Serialization helpers for routers
# --------------------------------------------------------------------------- #

def to_safe_dict(entry: ApiCatalogEntry, include_key: bool = False) -> Dict:
    """
    Convert a catalog entry to a JSON-serializable dict.

    Decrypts base_url and schema (admin-visible) but MASKS the API key by
    default. Pass include_key=True only for the reveal-for-copy flow,
    which the router must audit-log.
    """
    base_url = _decrypt(entry.encrypted_base_url) or ""
    schema = _decrypt(entry.encrypted_schema)
    api_key_plain = _decrypt(entry.encrypted_api_key)
    api_key_view = None
    if api_key_plain:
        api_key_view = api_key_plain if include_key else vault_service.mask_value(api_key_plain)

    return {
        "id": entry.id,
        "app_id": entry.app_id,
        "name": entry.name,
        "method": entry.method,
        "path": entry.path,
        "base_url": base_url,
        "full_url": base_url.rstrip("/") + (entry.path or "/"),
        "api_key": api_key_view,
        "has_api_key": api_key_plain is not None,
        "schema_snippet": (schema[:1000] if schema else None),
        "schema_size": len(schema) if schema else 0,
        "description": entry.description,
        "category": entry.category,
        "current_version": entry.current_version,
        "last_test_at": entry.last_test_at.isoformat() if entry.last_test_at else None,
        "last_test_status": entry.last_test_status,
        "last_test_message": entry.last_test_message,
        "last_test_http_code": entry.last_test_http_code,
        "last_test_latency_ms": entry.last_test_latency_ms,
        "is_active": entry.is_active,
        "discovery_source": entry.discovery_source,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def version_to_dict(v: ApiCatalogVersion) -> Dict:
    return {
        "id": v.id,
        "catalog_id": v.catalog_id,
        "version_number": v.version_number,
        "base_url": _decrypt(v.encrypted_base_url) or "",
        "has_api_key": bool(v.encrypted_api_key),
        "method": v.method,
        "path": v.path,
        "replaced_by_id": v.replaced_by_id,
        "reason": v.reason,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
