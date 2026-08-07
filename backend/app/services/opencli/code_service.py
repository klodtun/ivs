"""Code version service (P8) — persist generated code, deploy to IVS, export.

Every regeneration is a new OpenCliCodeVersion kept as history. Deploy reuses the
IVS app-deploy primitives (docker build + DNS). Delete is soft + audited, matching
the iVS standard for destructive actions.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    OpenCliImport,
    OpenCliCodeVersion,
    OpenCliCodeStatus,
)
from app.services.audit_service import create_audit_log


def _dir_sha256(code_dir: str) -> str:
    """Stable hash of a code set: sha of sorted (relpath, filebytes)."""
    h = hashlib.sha256()
    root = Path(code_dir)
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _next_version(db: Session, project_id: Optional[int], import_id: int) -> int:
    q = db.query(OpenCliCodeVersion)
    if project_id is not None:
        q = q.filter(OpenCliCodeVersion.project_id == project_id)
    else:
        q = q.filter(OpenCliCodeVersion.import_id == import_id)
    last = q.order_by(OpenCliCodeVersion.version.desc()).first()
    return (last.version + 1) if last else 1


def record(db: Session, imp: OpenCliImport, *, code_dir: str, provider: str,
           model: Optional[str], files_count: int, verify: Optional[dict],
           created_by: Optional[int], module: Optional[str] = None) -> OpenCliCodeVersion:
    """Persist a generated code set as a new version. Called by regen_service."""
    cv = OpenCliCodeVersion(
        project_id=imp.project_id or 0,   # 0 = unassigned (import-scoped versioning)
        import_id=imp.id,
        version=_next_version(db, imp.project_id, imp.id),
        module=module,
        provider=provider,
        model=model,
        files_count=files_count,
        code_dir=code_dir,
        sha256=_dir_sha256(code_dir),
        app_type=(verify or {}).get("app_type"),
        verify_ok=bool((verify or {}).get("ok")),
        status=OpenCliCodeStatus.GENERATED,
        created_by=created_by,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def list_versions(db: Session, *, project_id: Optional[int] = None,
                  import_id: Optional[int] = None) -> list[dict]:
    q = db.query(OpenCliCodeVersion).filter(
        OpenCliCodeVersion.status != OpenCliCodeStatus.DELETED)
    if project_id is not None:
        q = q.filter(OpenCliCodeVersion.project_id == project_id)
    if import_id is not None:
        q = q.filter(OpenCliCodeVersion.import_id == import_id)
    rows = q.order_by(OpenCliCodeVersion.version.desc()).all()
    return [{
        "id": c.id, "project_id": c.project_id, "import_id": c.import_id,
        "version": c.version, "module": c.module, "provider": c.provider, "model": c.model,
        "files_count": c.files_count, "app_type": c.app_type,
        "verify_ok": c.verify_ok, "status": c.status.value,
        "deployed_app_id": c.deployed_app_id, "sha256": c.sha256,
        "created_at": c.created_at.isoformat(),
    } for c in rows]


def list_deploys(db: Session, *, project_id: Optional[int] = None,
                 import_id: Optional[int] = None) -> list[dict]:
    """Merge+Deploy history: every merged app build (module='_all'), newest first,
    with its deploy status and the running app's slug/port/domain when deployed."""
    from app.models import App
    q = db.query(OpenCliCodeVersion).filter(
        OpenCliCodeVersion.module == "_all",
        OpenCliCodeVersion.status != OpenCliCodeStatus.DELETED)
    if project_id is not None:
        q = q.filter(OpenCliCodeVersion.project_id == project_id)
    if import_id is not None:
        q = q.filter(OpenCliCodeVersion.import_id == import_id)
    rows = q.order_by(OpenCliCodeVersion.version.desc()).all()
    out = []
    for c in rows:
        app = db.query(App).filter(App.id == c.deployed_app_id).first() if c.deployed_app_id else None
        out.append({
            "id": c.id, "version": c.version, "files_count": c.files_count,
            "status": c.status.value, "deployed_app_id": c.deployed_app_id,
            "app_slug": app.slug if app else None,
            "app_port": app.port if app else None,
            "app_domain": app.domain if app else None,
            "app_status": app.status.value if app else None,
            "created_at": c.created_at.isoformat(),
        })
    return out


def export_zip(cv: OpenCliCodeVersion) -> tuple[str, bytes]:
    """Zip the code version's files in memory. Returns (filename, bytes)."""
    if not cv.code_dir or not os.path.isdir(cv.code_dir):
        raise ValueError("code files not available")
    buf = io.BytesIO()
    root = Path(cv.code_dir)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(root))
    return f"opencli-code-v{cv.version}-{cv.id}.zip", buf.getvalue()


def delete_version(db: Session, cv: OpenCliCodeVersion, *, deleted_by: Optional[int],
                   reason: Optional[str], request=None, user=None) -> None:
    """Soft-delete a code version (kept as history row). Audited at WARNING."""
    cv.status = OpenCliCodeStatus.DELETED
    db.add(cv)
    if request is not None:
        create_audit_log(
            db, request, user, action="opencli_code_delete", resource_type="opencli",
            resource_id=str(cv.id),
            details=f"delete code v{cv.version} (project {cv.project_id}) reason={reason or '-'}",
            log_level="WARNING",
        )
    db.commit()


def merge_modules(db: Session, imp: OpenCliImport, *, created_by: Optional[int]) -> OpenCliCodeVersion:
    """Combine the latest code of every module into ONE deployable app dir.
    Each module's files go under modules/<module>/; a top-level index.html lists
    them so iVS deploys it as a static app. Recorded as a code version module='_all'."""
    # latest non-deleted module version — per-import, or project-scoped when this
    # is the combined project import (imp.id is None → the project's own module
    # code, which carries import_id NULL + project_id).
    q = db.query(OpenCliCodeVersion).filter(
        OpenCliCodeVersion.module.isnot(None),
        OpenCliCodeVersion.module != "_all",
        OpenCliCodeVersion.status != OpenCliCodeStatus.DELETED)
    if imp.id is None:
        q = q.filter(OpenCliCodeVersion.project_id == imp.project_id,
                     OpenCliCodeVersion.import_id.is_(None))
    else:
        q = q.filter(OpenCliCodeVersion.import_id == imp.id)
    rows = q.order_by(OpenCliCodeVersion.version.desc()).all()
    latest: dict[str, OpenCliCodeVersion] = {}
    for r in rows:
        latest.setdefault(r.module, r)
    if not latest:
        raise ValueError("no module code to merge — build modules first")

    base = os.path.join(imp.artifact_dir or ".", "code")
    n = 1
    while os.path.exists(os.path.join(base, f"merged{n}")):
        n += 1
    merged = Path(base) / f"merged{n}"
    merged.mkdir(parents=True, exist_ok=True)

    total_files = 0
    for module, cv in sorted(latest.items()):
        if not cv.code_dir or not os.path.isdir(cv.code_dir):
            continue
        dest = merged / "modules" / module
        shutil.copytree(cv.code_dir, dest, dirs_exist_ok=True)
        total_files += sum(len(f) for _r, _d, f in os.walk(dest))
        # per-module index so nginx serves the folder (else 403 on a dir listing)
        files = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
        links = "\n".join(f'<li><a href="{f}">{f}</a></li>' for f in files)
        (dest / "index.html").write_text(
            f"<!doctype html><meta charset='utf-8'><title>{module}</title>"
            f"<h1>Module: {module}</h1><p><a href='../../'>&larr; all modules</a></p>"
            f"<ul>{links}</ul>", encoding="utf-8")

    # top-level landing page → makes it a deployable static app
    items = "\n".join(
        f'<li><b>{m}</b> — code v{cv.version} ({cv.provider}) '
        f'<a href="modules/{m}/">open</a></li>'
        for m, cv in sorted(latest.items())
    )
    (merged / "index.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>{imp.source_ref}</title>"
        f"<h1>OpenCLI merged app</h1><p>{len(latest)} modules, {total_files} files.</p>"
        f"<ul>{items}</ul>", encoding="utf-8")

    cv = OpenCliCodeVersion(
        project_id=imp.project_id or 0, import_id=imp.id,
        version=_next_version(db, imp.project_id, imp.id), module="_all",
        provider="merge", model=None, files_count=total_files,
        code_dir=str(merged), sha256=_dir_sha256(str(merged)),
        app_type="static", verify_ok=True,
        status=OpenCliCodeStatus.GENERATED, created_by=created_by,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


async def deploy(db: Session, cv: OpenCliCodeVersion, *, name: str,
                 user, request) -> dict:
    """Deploy a code version as an IVS app, reusing the app-deploy primitives.
    Requires Docker. Copies the code into APPS_DIR, builds, and registers DNS."""
    # lazy imports: avoid a router<->router import cycle
    from app.config import settings
    from app.models import App, AppStatus, AppType, AppVersion, VaultKey
    from app.routers.apps import make_slug, allocate_port, _enforce_external_db_gate
    from app.services.docker_service import docker_service
    from app.services.dns_service import dns_service
    from app.services.vault_service import vault_service

    if not cv.code_dir or not os.path.isdir(cv.code_dir):
        raise ValueError("code files not available to deploy")

    slug = make_slug(name)
    source_path = os.path.join(settings.APPS_DIR, slug)
    os.makedirs(settings.APPS_DIR, exist_ok=True)
    if os.path.exists(source_path):
        shutil.rmtree(source_path)
    shutil.copytree(cv.code_dir, source_path)

    _enforce_external_db_gate(source_path)  # PRO/ENT DB gate, same as normal deploy

    port = allocate_port(db)
    app = App(name=name, slug=slug, description=f"OpenCLI regen v{cv.version}",
              owner_id=user.id, port=port, status=AppStatus.BUILDING, env_vars="{}")
    db.add(app)
    db.commit()
    db.refresh(app)

    try:
        app_type = docker_service.detect_app_type(source_path)
        app.app_type = {
            "nodejs": AppType.NODEJS, "python": AppType.PYTHON,
            "fullstack": AppType.FULLSTACK, "static": AppType.STATIC,
        }.get(app_type, AppType.UNKNOWN)
        app.source_path = source_path
        env = vault_service.build_env_dict(db.query(VaultKey).all())
        app.container_id = docker_service.build_and_run(slug, source_path, app_type, port, env)
        app.status = AppStatus.RUNNING
        app.domain = await dns_service.register_app(slug, port)
        db.add(AppVersion(app_id=app.id, version=1, commit_message=f"OpenCLI regen v{cv.version}"))
        cv.deployed_app_id = app.id
        cv.status = OpenCliCodeStatus.DEPLOYED
        db.add(cv)
        create_audit_log(
            db, request, user, action="opencli_deploy", resource_type="app",
            resource_id=str(app.id),
            details=f"deployed code v{cv.version} as {name} ({app_type})", log_level="WARNING",
        )
        db.commit()
    except Exception as e:
        app.status = AppStatus.ERROR
        db.commit()
        raise ValueError(f"deploy failed: {e}")

    return {"app_id": app.id, "slug": slug, "port": port, "status": app.status.value}
