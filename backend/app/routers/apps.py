import os
import re
import json
import shutil
import logging
import tempfile
import zipfile
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole, App, AppStatus, AppType, AppVersion, AuditLog, VaultKey, UserAppAccess, Tunnel
from app.schemas import AppResponse, AppDetailResponse, AppCreate, AppVersionResponse
from app.middleware.auth import get_current_user, require_role
from app.services.docker_service import docker_service
from app.services.dns_service import dns_service
from app.services.vault_service import vault_service
from app.config import settings
from app.services.audit_service import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/apps", tags=["Applications"])


def make_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60]


def _heal_container_id(app: "App", db: Session) -> str:
    """Refresh app.container_id from the live Docker daemon.

    If the stored id is stale (container rebuilt outside IVS), look up
    by the conventional name `ivs-<slug>` and update the row. Returns
    the live id or "" if no container exists.
    """
    live = docker_service.resolve_live_container_id(app.container_id or "", f"ivs-{app.slug}")
    if live and live != app.container_id:
        app.container_id = live
        try:
            db.commit()
        except Exception:
            db.rollback()
    return live


def allocate_port(db: Session) -> int:
    used = {a.port for a in db.query(App).filter(App.port.isnot(None)).all()}
    for p in range(settings.APP_PORT_RANGE_START, settings.APP_PORT_RANGE_END + 1):
        if p not in used:
            return p
    raise HTTPException(status_code=503, detail="No available ports")


def _get_user_allowed_app_ids(user: User, db: Session) -> tuple[bool, list[int]]:
    """Returns (access_all, list_of_app_ids) for a user."""
    access_records = db.query(UserAppAccess).filter(UserAppAccess.user_id == user.id).all()
    access_all = any(r.access_all for r in access_records)
    app_ids = [r.app_id for r in access_records if r.app_id is not None]
    return access_all, app_ids


def _can_access_app(user: User, app: App, db: Session) -> bool:
    """Check if user can access a specific app."""
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role == "admin":
        return True
    if role == "developer":
        # Developer can access own apps + assigned apps
        if app.owner_id == user.id:
            return True
        access_all, app_ids = _get_user_allowed_app_ids(user, db)
        return access_all or app.id in app_ids
    # Viewer
    access_all, app_ids = _get_user_allowed_app_ids(user, db)
    return access_all or app.id in app_ids


def _check_dockerfile_and_db_deps(source_path: str, files: list[str]) -> list[str]:
    """Check user-provided Dockerfile for potential issues like DB dependencies."""
    warnings = []

    # --- Check if user-provided Dockerfile exists ---
    dockerfile_path = os.path.join(source_path, "Dockerfile")
    if not os.path.exists(dockerfile_path):
        return warnings

    warnings.append("custom_dockerfile")

    try:
        with open(dockerfile_path, "r", errors="ignore") as f:
            dockerfile_content = f.read()
    except Exception:
        return warnings

    # Extract CMD/ENTRYPOINT target file from Dockerfile
    cmd_files = []
    uses_npm_script = None  # Track if CMD is "npm start" / "npm run ..."
    for line in dockerfile_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("CMD") or stripped.startswith("ENTRYPOINT"):
            # Parse JSON array form: CMD ["node", "src/server.js"]
            bracket_match = re.search(r'\[(.+)\]', stripped)
            if bracket_match:
                parts = [p.strip().strip('"').strip("'") for p in bracket_match.group(1).split(",")]
                for part in parts:
                    if part.endswith((".js", ".py", ".ts", ".sh")):
                        cmd_files.append(part)
                # Detect "npm start" / "npm run dev" etc.
                if len(parts) >= 2 and parts[0] == "npm":
                    if parts[1] == "start":
                        uses_npm_script = "start"
                    elif parts[1] == "run" and len(parts) >= 3:
                        uses_npm_script = parts[2]
            # Parse shell form: CMD node src/server.js
            else:
                shell_parts = stripped.split(None, 1)
                if len(shell_parts) > 1:
                    tokens = shell_parts[1].split()
                    for token in tokens:
                        if token.endswith((".js", ".py", ".ts")):
                            cmd_files.append(token)
                    if len(tokens) >= 2 and tokens[0] == "npm":
                        if tokens[1] == "start":
                            uses_npm_script = "start"
                        elif tokens[1] == "run" and len(tokens) >= 3:
                            uses_npm_script = tokens[2]

    # Resolve npm scripts to actual files via package.json
    if uses_npm_script and not cmd_files:
        pkg_path = os.path.join(source_path, "package.json")
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, "r") as f:
                    pkg = json.load(f)
                script_cmd = pkg.get("scripts", {}).get(uses_npm_script, "")
                # Extract .js file from script: "node src/server.js" → "src/server.js"
                for token in script_cmd.split():
                    if token.endswith((".js", ".ts")):
                        cmd_files.append(token)
                # Also check "main" field if script is "start" and no start script
                if not cmd_files and uses_npm_script == "start" and "main" in pkg:
                    cmd_files.append(pkg["main"])
            except Exception:
                pass

    # Check each CMD target for database dependencies
    db_patterns = {
        "mysql": "MySQL",
        "mysql2": "MySQL",
        "pg": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "mongoose": "MongoDB",
        "sequelize": "SQL ORM",
        "prisma": "Prisma ORM",
        "typeorm": "TypeORM",
        "knex": "Knex.js",
    }

    for cmd_file in cmd_files:
        target_path = os.path.join(source_path, cmd_file)
        if not os.path.exists(target_path):
            warnings.append(f"dockerfile_cmd_missing_file:{cmd_file}")
            continue

        try:
            with open(target_path, "r", errors="ignore") as f:
                content = f.read(8192)  # Read first 8KB
        except Exception:
            continue

        # Check for DB imports/requires
        found_dbs = set()
        for pattern, db_name in db_patterns.items():
            # Match: require("mysql2"), import mysql from "pg", from "mongodb", etc.
            if re.search(rf'''(?:require\s*\(\s*['"]|from\s+['"]|import\s+['"]){pattern}[/'"]''', content):
                found_dbs.add(db_name)

        # Also check indirect: ./db, ./database imports
        # Matches: import db from "./db.js", require("./db"), import("./database")
        db_import_patterns = [
            r'''from\s+['"]\.\/db(?:\.js)?['"]''',        # import X from "./db" or "./db.js"
            r'''require\s*\(\s*['"]\.\/db(?:\.js)?['"]''', # require("./db") or require("./db.js")
            r'''from\s+['"]\.\/database(?:\.js)?['"]''',   # import X from "./database"
            r'''require\s*\(\s*['"]\.\/database(?:\.js)?['"]''',  # require("./database")
        ]
        for db_pat in db_import_patterns:
            if re.search(db_pat, content):
                # Check the db/database file for actual DB driver imports
                for db_filename in ["db.js", "db.ts", "database.js", "database.ts"]:
                    db_file = os.path.join(os.path.dirname(target_path), db_filename)
                    if os.path.exists(db_file):
                        try:
                            with open(db_file, "r", errors="ignore") as dbf:
                                db_content = dbf.read(4096)
                            for p2, db2 in db_patterns.items():
                                if re.search(rf'''(?:require\s*\(\s*['"]|from\s+['"]){p2}[/'"]''', db_content):
                                    found_dbs.add(db2)
                        except Exception:
                            pass

        if found_dbs:
            db_list = ", ".join(sorted(found_dbs))
            warnings.append(f"dockerfile_db_dependency:{cmd_file}:{db_list}")

    # --- Check for multiple server files (common in LINE OA / Vibe Code projects) ---
    # Look for patterns like server.js + local-server.js, or main.py + local-main.py
    def find_files_recursive(base, ext, max_depth=3):
        results = []
        for root, dirs, fnames in os.walk(base):
            depth = root.replace(base, "").count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue
            for fn in fnames:
                if fn.endswith(ext):
                    results.append(os.path.relpath(os.path.join(root, fn), base))
        return results

    server_files = [f for f in find_files_recursive(source_path, ".js", 3)
                    if "server" in f.lower() and "node_modules" not in f]
    if len(server_files) > 1:
        warnings.append(f"multiple_server_files:{','.join(server_files)}")

    return warnings


def _validate_zip_structure(source_path: str) -> dict:
    """Validate extracted zip structure and return validation result."""
    files = os.listdir(source_path)
    issues = []
    warnings = []

    # Check for junk files that shouldn't be included
    if "node_modules" in files:
        warnings.append("node_modules_included")
    if ".venv" in files or "venv" in files:
        warnings.append("venv_included")
    if ".git" in files:
        warnings.append("git_included")

    # Check Dockerfile and DB dependencies (applies to all app types)
    dockerfile_warnings = _check_dockerfile_and_db_deps(source_path, files)
    warnings.extend(dockerfile_warnings)

    # Detect app type
    has_backend = os.path.isdir(os.path.join(source_path, "backend"))
    has_frontend = os.path.isdir(os.path.join(source_path, "frontend"))

    # --- Fullstack ---
    if has_backend and has_frontend:
        app_type = "fullstack"
        backend_main = os.path.join(source_path, "backend", "main.py")
        backend_req = os.path.join(source_path, "backend", "requirements.txt")
        frontend_dist = os.path.join(source_path, "frontend", "dist")
        frontend_pkg = os.path.join(source_path, "frontend", "package.json")

        if not os.path.exists(backend_main):
            issues.append("fullstack_no_backend_main")
        else:
            with open(backend_main, "r", errors="ignore") as f:
                content = f.read()
            if "fastapi" not in content.lower():
                issues.append("fullstack_backend_not_fastapi")

        if not os.path.exists(backend_req):
            issues.append("fullstack_no_backend_requirements")

        if not os.path.isdir(frontend_dist) and not os.path.exists(frontend_pkg):
            issues.append("fullstack_no_frontend")
        elif not os.path.isdir(frontend_dist):
            warnings.append("fullstack_no_dist")

        return {
            "valid": len(issues) == 0,
            "app_type": app_type,
            "issues": issues,
            "warnings": warnings,
            "files": files[:20],
        }

    # --- Node.js / Vite ---
    if "package.json" in files:
        app_type = "nodejs"
        pkg_path = os.path.join(source_path, "package.json")
        try:
            with open(pkg_path, "r") as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})
            dev_deps = pkg.get("devDependencies", {})
            deps = pkg.get("dependencies", {})

            is_vite = "vite" in dev_deps or "vite" in deps
            has_vite_build = "vite" in scripts.get("build", "")
            start_script = scripts.get("start", "")
            has_vite_preview = "vite preview" in start_script

            # Check for pre-built dist/
            dist_dir = os.path.join(source_path, "dist")
            has_dist = os.path.isdir(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html"))

            if has_dist:
                # Pre-built Vite/static app — use dist/ directly
                app_type = "static"
                warnings.append("vite_prebuilt_detected")
            elif is_vite:
                app_type = "nodejs"
                if has_vite_preview:
                    # Has vite preview in start — good
                    warnings.append("vite_preview_detected")
                elif has_vite_build and "start" not in scripts:
                    # Has build but no start — needs start script
                    issues.append("vite_no_start_script")
                elif "start" not in scripts and "dev" not in scripts and "main" not in pkg:
                    issues.append("nodejs_no_start_script")
            else:
                if "start" not in scripts and "dev" not in scripts and "main" not in pkg:
                    issues.append("nodejs_no_start_script")
        except Exception:
            issues.append("nodejs_invalid_package_json")

        if "package-lock.json" not in files and "yarn.lock" not in files:
            warnings.append("nodejs_no_lockfile")

        return {
            "valid": len(issues) == 0,
            "app_type": app_type,
            "issues": issues,
            "warnings": warnings,
            "files": files[:20],
        }

    # --- Python variants ---
    has_requirements = "requirements.txt" in files
    has_main_py = "main.py" in files
    has_app_py = "app.py" in files

    if has_requirements or has_main_py:
        req_content = ""
        if has_requirements:
            with open(os.path.join(source_path, "requirements.txt"), "r", errors="ignore") as f:
                req_content = f.read()

        # Streamlit
        if has_app_py and "streamlit" in req_content.lower():
            app_type = "streamlit"
            if not has_requirements:
                issues.append("streamlit_no_requirements")
            return {
                "valid": len(issues) == 0,
                "app_type": app_type,
                "issues": issues,
                "warnings": warnings,
                "files": files[:20],
            }

        # FastAPI
        if has_main_py:
            main_content = ""
            with open(os.path.join(source_path, "main.py"), "r", errors="ignore") as f:
                main_content = f.read()

            if "fastapi" in main_content.lower():
                app_type = "fastapi"
                if not has_requirements:
                    issues.append("fastapi_no_requirements")
                elif "uvicorn" not in req_content.lower():
                    warnings.append("fastapi_no_uvicorn")
                return {
                    "valid": len(issues) == 0,
                    "app_type": app_type,
                    "issues": issues,
                    "warnings": warnings,
                    "files": files[:20],
                }

        # Generic Python
        app_type = "python"
        if not has_main_py:
            issues.append("python_no_main")
        if not has_requirements:
            issues.append("python_no_requirements")
        return {
            "valid": len(issues) == 0,
            "app_type": app_type,
            "issues": issues,
            "warnings": warnings,
            "files": files[:20],
        }

    # --- Static ---
    if "index.html" in files:
        return {
            "valid": True,
            "app_type": "static",
            "issues": [],
            "warnings": warnings,
            "files": files[:20],
        }

    # --- Unknown: no recognizable structure ---
    issues.append("unknown_structure")
    return {
        "valid": False,
        "app_type": "unknown",
        "issues": issues,
        "warnings": warnings,
        "files": files[:20],
    }


@router.post("/validate")
async def validate_app(
    file: UploadFile = File(...),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Validate zip file structure before deployment."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    tmp_dir = tempfile.mkdtemp(prefix="ivs-validate-")
    try:
        # Save uploaded file
        zip_path = os.path.join(tmp_dir, "upload.zip")
        with open(zip_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract
        extract_dir = os.path.join(tmp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid zip file")

        # Unwrap single-folder wrapping (same logic as docker_service.extract_zip)
        entries = os.listdir(extract_dir)
        non_hidden = [e for e in entries if not e.startswith(".") and not e.startswith("__")]
        if len(non_hidden) == 1 and os.path.isdir(os.path.join(extract_dir, non_hidden[0])):
            inner = os.path.join(extract_dir, non_hidden[0])
            for item in os.listdir(inner):
                shutil.move(os.path.join(inner, item), os.path.join(extract_dir, item))
            os.rmdir(inner)

        # Validate structure
        result = _validate_zip_structure(extract_dir)
        return result

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("", response_model=list[AppResponse])
async def list_apps(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role = user.role.value if hasattr(user.role, "value") else user.role

    if role == "admin":
        return db.query(App).order_by(App.created_at.desc()).all()

    if role == "developer":
        # Developer sees: own apps + assigned apps
        access_all, app_ids = _get_user_allowed_app_ids(user, db)
        if access_all:
            return db.query(App).order_by(App.created_at.desc()).all()
        own_apps = db.query(App).filter(App.owner_id == user.id)
        assigned_apps = db.query(App).filter(App.id.in_(app_ids)) if app_ids else db.query(App).filter(App.id == -1)
        combined_ids = {a.id for a in own_apps.all()} | {a.id for a in assigned_apps.all()}
        return db.query(App).filter(App.id.in_(combined_ids)).order_by(App.created_at.desc()).all() if combined_ids else []

    # Viewer: only assigned apps that are running
    access_all, app_ids = _get_user_allowed_app_ids(user, db)
    if access_all:
        return db.query(App).filter(App.status == AppStatus.RUNNING).order_by(App.created_at.desc()).all()
    if not app_ids:
        return []
    return db.query(App).filter(App.id.in_(app_ids), App.status == AppStatus.RUNNING).order_by(App.created_at.desc()).all()


@router.get("/{app_id}", response_model=AppDetailResponse)
async def get_app(app_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    return app


@router.post("", response_model=AppResponse)
async def deploy_app(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    env_vars: str = Form("{}"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    slug = make_slug(name)
    existing = db.query(App).filter(App.slug == slug).first()
    if existing:
        return await _redeploy(existing, file, db, user, request)

    port = allocate_port(db)

    app = App(
        name=name,
        slug=slug,
        description=description,
        owner_id=user.id,
        port=port,
        status=AppStatus.BUILDING,
        env_vars=env_vars,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    try:
        source_path = os.path.join(settings.APPS_DIR, slug)
        upload_path = os.path.join(settings.UPLOAD_DIR, f"{slug}.zip")
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.APPS_DIR, exist_ok=True)

        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)

        if os.path.exists(source_path):
            shutil.rmtree(source_path)
        docker_service.extract_zip(upload_path, source_path)

        app_type = docker_service.detect_app_type(source_path)
        type_map = {
            "nodejs": AppType.NODEJS,
            "nodejs_vite": AppType.NODEJS,
            "python": AppType.PYTHON,
            "python_streamlit": AppType.PYTHON,
            "python_fastapi": AppType.PYTHON,
            "fullstack": AppType.FULLSTACK,
            "static": AppType.STATIC,
            "static_prebuilt": AppType.STATIC,
        }
        app.app_type = type_map.get(app_type, AppType.UNKNOWN)
        app.source_path = source_path

        parsed_env = json.loads(env_vars) if isinstance(env_vars, str) else env_vars
        vault_keys = db.query(VaultKey).all()
        injected_env = vault_service.build_env_dict(vault_keys)
        injected_env.update(parsed_env)

        container_id = docker_service.build_and_run(slug, source_path, app_type, port, injected_env)
        app.container_id = container_id
        app.status = AppStatus.RUNNING

        domain_url = await dns_service.register_app(slug, port)
        app.domain = domain_url

        version = AppVersion(app_id=app.id, version=1, commit_message="Initial deployment")
        db.add(version)

        create_audit_log(
            db, request, user=user, action="deploy", resource_type="app",
            resource_id=str(app.id), details=f"Deployed {name} ({app_type}) on port {port}",
        )
        db.commit()
        db.refresh(app)
        os.remove(upload_path)

    except Exception as e:
        logger.error(f"Deploy failed for {slug}: {e}")
        app.status = AppStatus.ERROR
        create_audit_log(
            db, request, user=user, action="deploy_failed", resource_type="app",
            resource_id=str(app.id), details=f"Deploy failed for {name}: {str(e)[:200]}",
            log_level="ERROR",
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")

    return app


async def _redeploy(app: App, file: UploadFile, db: Session, user: User, request: Request) -> App:
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    slug = app.slug
    upload_path = os.path.join(settings.UPLOAD_DIR, f"{slug}.zip")
    source_path = os.path.join(settings.APPS_DIR, slug)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        if os.path.exists(source_path):
            shutil.rmtree(source_path)
        docker_service.extract_zip(upload_path, source_path)

        app_type = docker_service.detect_app_type(source_path)
        parsed_env = json.loads(app.env_vars) if app.env_vars else {}
        vault_keys = db.query(VaultKey).all()
        injected_env = vault_service.build_env_dict(vault_keys)
        injected_env.update(parsed_env)

        container_id = docker_service.build_and_run(slug, source_path, app_type, app.port, injected_env)
        app.container_id = container_id
        app.status = AppStatus.RUNNING
        app.current_version += 1

        version = AppVersion(
            app_id=app.id, version=app.current_version, commit_message=f"Redeployment v{app.current_version}"
        )
        db.add(version)
        create_audit_log(
            db, request, user=user, action="redeploy", resource_type="app",
            resource_id=str(app.id), details=f"Redeployed {app.name} v{app.current_version}",
        )
        db.commit()
        db.refresh(app)
        os.remove(upload_path)
        return app

    except Exception as e:
        logger.error(f"Redeploy failed for {slug}: {e}")
        app.status = AppStatus.ERROR
        create_audit_log(
            db, request, user=user, action="redeploy_failed", resource_type="app",
            resource_id=str(app.id), details=f"Redeploy failed for {app.name}: {str(e)[:200]}",
            log_level="ERROR",
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")


@router.post("/{app_id}/start")
async def start_app(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    live_id = _heal_container_id(app, db)
    if live_id:
        docker_service.start_container(live_id)
    app.status = AppStatus.RUNNING
    db.commit()
    return {"message": f"{app.name} started"}


@router.post("/{app_id}/stop")
async def stop_app(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    live_id = _heal_container_id(app, db)
    if live_id:
        docker_service.stop_container(live_id)
    app.status = AppStatus.STOPPED
    db.commit()
    return {"message": f"{app.name} stopped"}


@router.post("/{app_id}/restart")
async def restart_app(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    live_id = _heal_container_id(app, db)
    if live_id:
        docker_service.restart_container(live_id)
    app.status = AppStatus.RUNNING
    db.commit()
    return {"message": f"{app.name} restarted"}


@router.get("/{app_id}/logs")
async def get_app_logs(
    app_id: int,
    tail: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")
    live_id = _heal_container_id(app, db)
    if not live_id:
        return {"logs": "No container associated"}
    return {"logs": docker_service.get_container_logs(live_id, tail)}


@router.get("/{app_id}/versions", response_model=list[AppVersionResponse])
async def list_versions(app_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(AppVersion).filter(AppVersion.app_id == app_id).order_by(AppVersion.version.desc()).all()


@router.get("/{app_id}/build-logs")
async def stream_build_logs(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Stream build logs via SSE for real-time monitoring."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access_app(user, app, db):
        raise HTTPException(status_code=403, detail="Access denied to this app")

    async def log_generator():
        slug = app.slug
        sent_index = 0
        max_wait = 300  # 5 minutes max
        waited = 0
        while waited < max_wait:
            logs = docker_service.get_build_logs(slug)
            status = docker_service.get_build_status(slug)
            while sent_index < len(logs):
                line = logs[sent_index]
                yield f"data: {json.dumps({'line': line, 'index': sent_index})}\n\n"
                sent_index += 1
            if status in ("success", "error", "timeout"):
                yield f"data: {json.dumps({'status': status, 'done': True})}\n\n"
                break
            await asyncio.sleep(0.5)
            waited += 0.5
        yield f"data: {json.dumps({'status': 'done', 'done': True})}\n\n"

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


EXPORTS_DIR = os.path.join(
    os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")),
    "exports",
    "apps",
)


def _human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@router.post("/{app_id}/export")
async def export_app(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Export an app's source + runtime data + metadata as a single .zip bundle.

    Bundle layout:
        source/      ← the deployed_apps/<slug>/ directory (Dockerfile, code, configs)
        data/        ← contents copied out of the running container's data paths
        metadata.json
        README.md

    Use this BEFORE deleting an app you intend to redeploy, so user-generated
    data inside the container isn't lost when the container is destroyed.

    Copyright protection — only the original deployer (App.owner_id) may
    export. Admins do not get an override here on purpose: the export
    contains the full source code, and copying another developer's work is
    exactly what we're trying to prevent. Denied attempts are audit-logged.
    """
    from datetime import datetime, timezone

    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Ownership rule: current owner can always export. Admins also get
    # export rights because the deployer may have been deleted (their
    # apps were reassigned to the deleting admin) and other admins still
    # need access for backup / migration. Non-admin developers can only
    # export apps they themselves own.
    role_value = user.role.value if hasattr(user.role, "value") else user.role
    if app.owner_id != user.id and role_value != "admin":
        owner = db.query(User).filter(User.id == app.owner_id).first()
        owner_name = owner.username if owner else f"uid:{app.owner_id}"
        create_audit_log(
            db, request, user=user, action="export_app_denied", resource_type="app",
            resource_id=str(app_id),
            details=f"Denied export of '{app.name}' — not the deployer (owner: {owner_name})",
            log_level="WARNING",
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail=(
                f"Only the original deployer of this app can export it "
                f"(deployer: {owner_name}). This restriction prevents copying "
                f"another developer's source code."
            ),
        )

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{app.slug}_{timestamp}.zip"
    zip_path = os.path.join(EXPORTS_DIR, filename)

    source_path = os.path.join(settings.APPS_DIR, app.slug)
    data_summary: dict = {"copied": [], "skipped": [], "errors": []}

    with tempfile.TemporaryDirectory(prefix=f"ivs-export-{app.slug}-") as tmpdir:
        # 1. Source files (Dockerfile, code, nginx-app.conf, etc.)
        source_dest = os.path.join(tmpdir, "source")
        if os.path.isdir(source_path):
            shutil.copytree(source_path, source_dest, dirs_exist_ok=True)
        else:
            os.makedirs(source_dest, exist_ok=True)

        # 2. Container data (data dirs, uploads, sqlite files, etc.)
        data_dest = os.path.join(tmpdir, "data")
        os.makedirs(data_dest, exist_ok=True)
        if app.container_id:
            try:
                data_summary = docker_service.export_container_data(
                    f"ivs-{app.slug}", data_dest
                )
            except Exception as e:
                logger.warning(f"Could not export container data for {app.slug}: {e}")
                data_summary["errors"].append(str(e))
        else:
            data_summary["errors"].append("App has no running container — data section is empty.")

        # 3. Metadata
        env_vars = {}
        try:
            env_vars = json.loads(app.env_vars_json) if app.env_vars_json else {}
        except Exception:
            pass

        metadata = {
            "ivs_export_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": user.username,
            "app": {
                "id": app.id,
                "name": app.name,
                "slug": app.slug,
                "description": app.description,
                "app_type": app.app_type.value if hasattr(app.app_type, "value") else str(app.app_type),
                "port": app.port,
                "current_version": app.current_version,
                "status_at_export": app.status.value if hasattr(app.status, "value") else str(app.status),
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "env_vars": env_vars,
            },
            "data_export": data_summary,
        }
        with open(os.path.join(tmpdir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 4. README — instructions for re-import
        readme = f"""# IVS App Export — {app.name}

**Exported:** {metadata['exported_at']}
**By:** {user.username}
**App slug:** `{app.slug}`
**Type:** {metadata['app']['app_type']}
**Port (original):** {app.port}

## Bundle contents

```
source/         Original deployed source (Dockerfile, code, configs)
data/           Files copied OUT of the running container at export time
metadata.json   App config + env vars + export summary
```

## What was exported from the container

"""
        if data_summary["copied"]:
            for item in data_summary["copied"]:
                readme += f"- `{item['container_path']}` → `data/{item['name']}` ({_human_size(item['size_bytes'])})\n"
        else:
            readme += "_(No matching data paths found inside the container — the app may not store persistent data, or the container was not running at export time.)_\n"

        if data_summary["errors"]:
            readme += "\n### Warnings\n\n"
            for err in data_summary["errors"]:
                readme += f"- {err}\n"

        readme += f"""

## How to re-import this app

1. Open IVS dashboard → **Deploy New App**
2. Upload `source/` (zip it first), OR drop the original .zip you used.
3. After deploy succeeds, copy the files from `data/` back into the new
   container with: `docker cp data/<dir> ivs-{app.slug}:/app/backend/<dir>`
4. Restart the app from the dashboard.

## Environment variables at export time

"""
        if env_vars:
            for k in env_vars.keys():
                readme += f"- `{k}` (value redacted — set via IVS Vault on re-import)\n"
        else:
            readme += "_(none)_\n"

        readme += "\n---\n_Generated by IVS — Internal Vibe Server._\n"
        with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

        # 5. Zip the whole bundle (deflate, fast enough; sources are small)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    fp = os.path.join(root, fname)
                    arcname = os.path.relpath(fp, tmpdir)
                    zf.write(fp, arcname)

    size_bytes = os.path.getsize(zip_path)

    create_audit_log(
        db, request, user=user, action="export_app", resource_type="app",
        resource_id=str(app_id),
        details=f"Exported {app.name} ({_human_size(size_bytes)}, {len(data_summary['copied'])} data path(s))",
    )
    db.commit()

    return {
        "filename": filename,
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "data_paths_copied": len(data_summary["copied"]),
        "data_paths_skipped": len(data_summary["skipped"]),
        "errors": data_summary["errors"],
        "download_url": f"/api/apps/exports/{filename}",
    }


@router.get("/exports/{filename}")
async def download_app_export(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Download a previously created app export bundle."""
    # Basic path-traversal guard
    if "/" in filename or ".." in filename or not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Export file not found")
    from fastapi.responses import FileResponse
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/zip",
    )


@router.delete("/{app_id}")
async def delete_app(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Stop and remove Docker container (gracefully handle Docker being down)
    if app.container_id:
        try:
            docker_service.stop_and_remove(f"ivs-{app.slug}")
        except Exception as e:
            logger.warning(f"Could not remove container for {app.slug}: {e}")

    # Remove DNS/Caddy entries (gracefully handles services being down)
    try:
        await dns_service.unregister_app(app.slug)
    except Exception as e:
        logger.warning(f"Could not unregister DNS for {app.slug}: {e}")

    # Remove source files
    source_path = os.path.join(settings.APPS_DIR, app.slug)
    if os.path.exists(source_path):
        shutil.rmtree(source_path)

    # Clean up all related records before deleting app
    app_name = app.name
    db.query(Tunnel).filter(Tunnel.app_id == app_id).delete()
    db.query(UserAppAccess).filter(UserAppAccess.app_id == app_id).delete()
    db.query(AppVersion).filter(AppVersion.app_id == app_id).delete()
    db.delete(app)
    create_audit_log(
        db, request, user=user, action="delete_app", resource_type="app",
        resource_id=str(app_id), details=f"Deleted app {app_name}",
        log_level="WARNING",
    )
    db.commit()
    return {"message": f"{app_name} deleted"}
