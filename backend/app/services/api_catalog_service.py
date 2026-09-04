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
    """Build the in-network URL to reach the app's API root.

    An app in `protected` mode does not answer on `App.port` — the login gate
    does, and the gate wants a browser session this probe will never have. The
    container itself binds the shadow port. Calling the public port instead
    reports a healthy app as unreachable, which is worse than no check at all:
    a flow step reads BROKEN and whoever sees it goes looking for a fault in
    the app rather than in the probe.

    `exchange_gateway_service` already resolves the address this way. This is
    the same rule, applied where the catalog and the flow verifier read it.
    """
    if not app.port:
        return None
    from app.services.app_gate_service import internal_port
    port = internal_port(app.port) if app.access_mode == "protected" else app.port
    return f"http://localhost:{port}"


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


def scan_app(db: Session, app: App) -> Dict:
    """
    Discover one app's API root and upsert its catalog entry.

    Does not commit — the caller decides when. Returns a result dict with a
    ``status`` of NEW, UPDATED or NO_PORT, plus ``schema_changed`` when the
    app's API shape moved under an entry that already existed.
    """
    result: Dict = {"slug": app.slug, "status": "NO_PORT", "schema_changed": False}

    base_url = _app_base_url(app)
    if not base_url:
        return result

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
        # A redeploy can change the app's API. Any MCP tool generated from
        # the old shape would keep calling it and return answers that are
        # wrong without being errors, so park the tool until the new schema
        # is confirmed.
        from app.services.mcp_service import check_drift
        if check_drift(db, existing, existing.method or "GET", existing.path or "/", schema_str or ""):
            result["schema_changed"] = True
        result["status"] = "UPDATED"
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
        result["status"] = "NEW"

    return result


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
        result = scan_app(db, app)
        if result["status"] == "NO_PORT":
            summary["failed"] += 1
        elif result["status"] == "NEW":
            summary["new"] += 1
        else:
            summary["updated"] += 1
        if result.get("schema_changed"):
            summary.setdefault("schema_changed", []).append(app.slug)
        summary["details"].append({"slug": app.slug, "status": result["status"]})

    db.commit()
    return summary


# --------------------------------------------------------------------------- #
# Scan triggered by a lifecycle change
# --------------------------------------------------------------------------- #

# A container is up before the process inside it is listening. Give the app a
# moment before asking it for its schema, or every first scan reads NO_PORT and
# the catalog stays empty until someone presses the button by hand.
POST_DEPLOY_SCAN_DELAY = 6.0


def scan_after_lifecycle_change(app_id: int, delay: float = POST_DEPLOY_SCAN_DELAY) -> None:
    """
    Schedule a catalog scan for one app, off the request path.

    The catalog exists so nobody has to remember to fill it in, so it is
    refreshed by deploy, redeploy, start and restart rather than by a button.
    Discovery makes blocking HTTP calls and the app may not answer at all, so
    this never runs inline: a deploy must not get slower, and must never fail,
    because discovery did.
    """
    import asyncio

    async def _run() -> None:
        await asyncio.sleep(delay)
        # Own session, per the rule that background work never borrows the
        # request's session — that one is closed by the time this wakes up.
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            app = db.query(App).filter(App.id == app_id).first()
            if not app or app.status != AppStatus.RUNNING:
                return
            result = scan_app(db, app)
            # เส้นเชื่อมเปลี่ยนพร้อมกับแอป จึงหาใหม่ในรอบเดียวกัน
            try:
                from app.services import dependency_service
                dep = dependency_service.discover_for_app(db, app)
            except Exception as e:
                dep = {"new": 0}
                logger.warning("หาเส้นเชื่อมของ %s ไม่สำเร็จ: %s", app.slug, e)
            db.commit()
            logger.info(
                "API catalog scan for %s: %s (เส้นเชื่อมใหม่ %d)",
                app.slug, result["status"], dep.get("new", 0),
            )
            if result.get("schema_changed"):
                logger.warning(
                    "API shape of %s changed — MCP tools built from the old "
                    "schema are parked until confirmed", app.slug
                )
        except Exception as e:
            db.rollback()
            logger.warning("API catalog scan failed for app %s: %s", app_id, e)
        finally:
            db.close()

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        # No event loop (a sync context or a test). Skip rather than block —
        # the manual scan and the next lifecycle change both still work.
        logger.debug("No running loop; skipped catalog scan for app %s", app_id)


# --------------------------------------------------------------------------- #
# Test
# --------------------------------------------------------------------------- #

def _probe(url: str, method: str, headers: Dict) -> Dict:
    """ยิงคำขอหนึ่งครั้งแล้วคืนผล — ไม่แตะฐานข้อมูล

    แยกออกจาก test_entry เพื่อให้ยิงหลายปลายทางพร้อมกันได้จากหลายเธรด
    Session ของ SQLAlchemy ใช้ข้ามเธรดไม่ได้ การเขียนผลจึงต้องกลับมาทำที่เธรด
    หลักเสมอ
    """
    start = time.monotonic()
    result = {"status": "FAIL", "http_code": None, "latency_ms": 0, "message": "", "body_snippet": ""}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            r = client.request(method, url, headers=headers)
        elapsed = int((time.monotonic() - start) * 1000)
        result["http_code"] = r.status_code
        result["latency_ms"] = elapsed
        result["body_snippet"] = (r.text or "")[:500]
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
    return result


def _request_parts(entry: ApiCatalogEntry):
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
    return url, (entry.method or "GET").upper(), headers


def _record(entry: ApiCatalogEntry, result: Dict) -> None:
    entry.last_test_at = _utcnow()
    entry.last_test_status = result["status"]
    entry.last_test_message = result["message"]
    entry.last_test_http_code = result["http_code"]
    entry.last_test_latency_ms = result["latency_ms"]


def test_entry(db: Session, entry: ApiCatalogEntry) -> Dict:
    """
    Call the API endpoint and record the result on the entry.

    Returns: {status, http_code, latency_ms, message, body_snippet}
    """
    url, method, headers = _request_parts(entry)
    result = _probe(url, method, headers)
    _record(entry, result)
    db.commit()
    return result


def test_entries(db: Session, entries: List[ApiCatalogEntry]) -> Dict:
    """ตรวจหลายปลายทางพร้อมกัน แล้วเขียนผลรวดเดียว

    ตรวจทีละตัวแบบเรียงกันจะใช้เวลาเท่ากับผลรวมของ timeout ทุกตัว ซึ่งกับสิบห้า
    แอปที่บางตัวไม่ตอบ กลายเป็นนานเกินกว่าที่คนจะรอหน้าจอค้าง
    """
    from concurrent.futures import ThreadPoolExecutor

    if not entries:
        return {"tested": 0, "ok": 0, "fail": 0, "results": {}}

    jobs = [(e, *_request_parts(e)) for e in entries]
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        outcomes = list(pool.map(lambda j: _probe(j[1], j[2], j[3]), jobs))

    results = {}
    for (entry, *_), result in zip(jobs, outcomes):
        _record(entry, result)
        if entry.app_id is not None:
            results[entry.app_id] = result
    db.commit()
    return {
        "tested": len(outcomes),
        "ok": sum(1 for r in outcomes if r["status"] == "OK"),
        "fail": sum(1 for r in outcomes if r["status"] != "OK"),
        "results": results,
    }


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
