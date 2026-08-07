"""OpenCLI Bridge router (Pro/Enterprise).

Read a legacy source (read-only), strip PII, emit OpenCLI artifacts, and manage
strict import + deletion history. See docs/opencli-bridge-architecture.md.

Edition gate: PRO/ENT only (reuses license_service.EDITIONS_WITH_EXTERNAL_DB).
Destructive delete requires password re-auth, mirroring the retention purge.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_role, verify_password
from app.models import (
    OpenCliImport,
    OpenCliImportDeletion,
    OpenCliPiiProfile,
    User,
    UserRole,
)
from app.services import license_service, audit_service
from app.services.opencli import (
    pipeline, reader, roundtrip, vector, regen, preflight, regen_service, project_service,
    code_service, mcp_token_service, chat_service, code_analyzer, modules as modules_svc,
    llm_models_service, project_ops,
)
from app.models import VaultKey
from app.models import (
    OpenCliCodeVersion, OpenCliProject, OpenCliMcpToken, OpenCliImportStatus,
    OpenCliCodeStatus, App, AppStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/opencli", tags=["opencli-bridge"])

# Edition gate — the bridge is a Pro/Enterprise feature.
_BRIDGE_EDITIONS = license_service.EDITIONS_WITH_EXTERNAL_DB  # {"PRO", "ENT"}


def _require_bridge_edition() -> None:
    ed = license_service.current_edition()
    if ed not in _BRIDGE_EDITIONS:
        raise HTTPException(
            status_code=403,
            detail=f"OpenCLI Bridge requires a Pro or Enterprise license (current: {ed}).",
        )


def _require_vector_edition() -> None:
    if not license_service.edition_supports_vector_index():
        raise HTTPException(
            status_code=403,
            detail=f"AI retrieval index requires an Enterprise license "
                   f"(current: {license_service.current_edition()}).",
        )


def _load_import(db: Session, import_id: int) -> OpenCliImport:
    imp = reader.get_import(db, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="import not found")
    if not imp.artifact_dir:
        raise HTTPException(status_code=409, detail="import not yet transformed")
    return imp


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class ImportCreate(BaseModel):
    source_kind: str = "sqlite"          # sqlite (P1) | rest (P2)
    source_ref: str                      # path/url — reference only
    pii_profile: OpenCliPiiProfile = OpenCliPiiProfile.EXCLUDE
    project_id: Optional[int] = None     # which project/app this import belongs to


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ModuleGenRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    module: str
    model_id: Optional[int] = None   # which registered AI builds it (multi-agent)


class MergeDeployRequest(BaseModel):
    name: str
    deploy: bool = True


class ImportOut(BaseModel):
    id: int
    project_id: Optional[int]
    importer_id: Optional[int]
    source_kind: str
    source_ref: str
    source_bytes: int
    sha256_raw: str
    pii_profile: OpenCliPiiProfile
    status: str
    artifact_dir: Optional[str]
    manifest_sha: Optional[str]
    command_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class DeletionOut(BaseModel):
    id: int
    import_id: int
    deleted_by: Optional[int]
    reason: Optional[str]
    sha256_raw: str
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeleteRequest(BaseModel):
    password: str                        # re-auth, like retention purge
    reason: Optional[str] = None


def _to_out(imp: OpenCliImport) -> ImportOut:
    return ImportOut(
        id=imp.id, project_id=imp.project_id,
        importer_id=imp.importer_id, source_kind=imp.source_kind,
        source_ref=imp.source_ref, source_bytes=imp.source_bytes,
        sha256_raw=imp.sha256_raw, pii_profile=imp.pii_profile,
        status=imp.status.value, artifact_dir=imp.artifact_dir,
        manifest_sha=imp.manifest_sha, command_count=imp.command_count,
        created_at=imp.created_at,
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

class ChatRequest(BaseModel):
    message: str
    project_id: Optional[int] = None


@router.get("/dashboard")
async def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Control-center summary — counts + provider status for the hero cards."""
    _require_bridge_edition()
    projects = db.query(OpenCliProject).count()
    imports = db.query(OpenCliImport).filter(
        OpenCliImport.status != OpenCliImportStatus.DELETED).count()
    code = db.query(OpenCliCodeVersion).filter(
        OpenCliCodeVersion.status != OpenCliCodeStatus.DELETED).count()
    deployed = db.query(OpenCliCodeVersion).filter(
        OpenCliCodeVersion.status == OpenCliCodeStatus.DEPLOYED).count()
    tokens = db.query(OpenCliMcpToken).filter(OpenCliMcpToken.revoked_at.is_(None)).count()
    llm = regen_service.get_config(db)
    return {
        "projects": projects,
        "imports": imports,
        "code_versions": code,
        "deployed": deployed,
        "active_tokens": tokens,
        "provider": llm["provider"],
        "provider_has_key": llm["has_key"],
        "edition": license_service.current_edition(),
    }


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Natural-language chat grounded on a project's OpenCLI manifest."""
    _require_bridge_edition()
    try:
        return chat_service.chat(db, project_id=body.project_id, message=body.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


# --------------------------------------------------------------------------- #
# Project-level operations (P16) — one project/app is the unit of work.
# Additive: per-import endpoints above are untouched (fallback).
# --------------------------------------------------------------------------- #

def _load_project(db: Session, project_id: int):
    p = project_service.get(db, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return p


@router.get("/projects/{project_id}/modules")
async def project_modules(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Modules of the whole project (union of all its imports' manifests)."""
    _require_bridge_edition()
    p = _load_project(db, project_id)
    try:
        return modules_svc.list_modules(project_ops.build_combined(db, p))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/projects/{project_id}/regen/module")
async def project_regen_module(
    project_id: int,
    body: ModuleGenRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Generate ONE module at project scope (combined manifest)."""
    _require_bridge_edition()
    p = _load_project(db, project_id)
    try:
        combined = project_ops.build_combined(db, p)
        result = regen_service.generate_module(
            db, combined, body.module, created_by=user.id, model_id=body.model_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"module gen failed: {str(e)[:300]}")
    try:
        audit_service.create_audit_log(
            db, request, user, action="opencli_project_regen_module",
            resource_type="opencli", resource_id=str(project_id),
            details=f"project={project_id} module={body.module} files={result['files']}",
            log_level="WARNING")
    except Exception:
        db.rollback()
    return result


@router.get("/projects/{project_id}/code")
async def project_code(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Project-level code versions (import_id NULL)."""
    _require_bridge_edition()
    _load_project(db, project_id)
    rows = code_service.list_versions(db, project_id=project_id)
    return [r for r in rows if r["import_id"] is None]


@router.get("/projects/{project_id}/gen-attempts")
async def project_gen_attempts(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Module-generation attempt history (errors + successes) for a project."""
    _require_bridge_edition()
    _load_project(db, project_id)
    return regen_service.list_attempts(db, project_id=project_id)


@router.get("/projects/{project_id}/deploys")
async def project_deploys(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge+Deploy history for a project."""
    _require_bridge_edition()
    _load_project(db, project_id)
    return code_service.list_deploys(db, project_id=project_id)


@router.get("/projects/{project_id}/structure")
async def project_structure(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    p = _load_project(db, project_id)
    try:
        combined = project_ops.build_combined(db, p)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"project_id": project_id, "structure_md": reader.read_structure_md(combined) or ""}


@router.get("/projects/{project_id}/roundtrip")
async def project_roundtrip(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregate round-trip fidelity across the project's imports."""
    _require_bridge_edition()
    p = _load_project(db, project_id)
    imps = project_ops.project_imports(db, project_id)
    if not imps:
        raise HTTPException(status_code=409, detail="no transformed imports")
    reports, tt, tm, ce, cc, pii, defects = [], 0, 0, 0, 0, 0, []
    for imp in imps:
        r = roundtrip.run(db, imp)
        reports.append({"import_id": imp.id, "fidelity": round(r.fidelity, 4),
                        "tables": f"{r.tables_matched}/{r.tables_total}"})
        tt += r.tables_total; tm += r.tables_matched
        ce += r.columns_expected; cc += r.columns_correct; pii += r.pii_dropped
        defects += [d for d in r.as_dict()["defects"]]
    return {
        "site": p.slug, "project_id": project_id, "imports": len(imps),
        "fidelity": round(cc / ce, 4) if ce else 1.0,
        "tables_matched": tm, "tables_total": tt,
        "columns_correct": cc, "columns_expected": ce, "pii_dropped": pii,
        "passed": tm == tt and cc == ce, "defects": defects, "per_import": reports,
    }


@router.post("/projects/{project_id}/merge-deploy")
async def project_merge_deploy(
    project_id: int,
    body: MergeDeployRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Merge the project's module code into one app, then (optionally) deploy."""
    _require_bridge_edition()
    p = _load_project(db, project_id)
    try:
        combined = project_ops.build_combined(db, p)
        cv = code_service.merge_modules(db, combined, created_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = {"merged_code_id": cv.id, "version": cv.version,
              "files": cv.files_count, "deploy": None}
    if body.deploy:
        try:
            result["deploy"] = await code_service.deploy(
                db, cv, name=body.name, user=user, request=request)
        except Exception as e:
            result["deploy_error"] = str(e)[:300]
    audit_service.create_audit_log(
        db, request, user, action="opencli_project_merge", resource_type="opencli",
        resource_id=str(project_id), details=f"merged project {project_id} → v{cv.version}",
        log_level="WARNING")
    return result


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Delete a project (cascades to its imports/code/tokens)."""
    _require_bridge_edition()
    p = _load_project(db, project_id)
    db.delete(p)
    db.commit()
    audit_service.create_audit_log(
        db, request, user, action="opencli_project_delete", resource_type="opencli",
        resource_id=str(project_id), details=f"deleted project '{p.name}'", log_level="WARNING")
    return {"ok": True}


@router.get("/projects")
async def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    return project_service.list_projects(db)


class AnalyzeCodeRequest(BaseModel):
    path: str


@router.post("/projects/{project_id}/analyze-code")
async def analyze_project_code(
    project_id: int,
    body: AnalyzeCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Analyze a legacy source folder → code map (the 'โค้ดเดิม' regen input).
    Raw code is NOT stored; secrets are detected and excluded."""
    _require_bridge_edition()
    if project_service.get(db, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    path = body.path[len("file://"):] if body.path.startswith("file://") else body.path
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"folder not found: {body.path}")
    rep = code_analyzer.analyze(path)
    # store the derived map only (no raw code)
    with open(code_analyzer.project_map_path(project_id), "w", encoding="utf-8") as f:
        f.write(rep.code_map_md)
    audit_service.create_audit_log(
        db, request, user, action="opencli_code_analyze", resource_type="opencli",
        resource_id=str(project_id),
        details=f"analyzed {rep.files} files, {len(rep.secrets)} secrets excluded",
        log_level="WARNING",
    )
    return rep.as_dict()


@router.post("/projects")
async def create_project(
    body: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    _require_bridge_edition()
    p = project_service.create(db, name=body.name, description=body.description, owner_id=user.id)
    audit_service.create_audit_log(
        db, request, user, action="opencli_project_create", resource_type="opencli",
        resource_id=str(p.id), details=f"project '{p.name}' ({p.slug})", log_level="INFO",
    )
    return {"id": p.id, "name": p.name, "slug": p.slug}


@router.post("/imports/preflight")
async def preflight_import(
    body: ImportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Pre-flight Advisor — inspect the source read-only and recommend settings.
    No data is read for transform, hashed, or persisted."""
    _require_bridge_edition()
    try:
        return preflight.run(body.source_kind, body.source_ref).as_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/imports", response_model=ImportOut)
async def create_import(
    body: ImportCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Stage 1->2->3->5: read source read-only, hash it, emit artifacts, log history."""
    _require_bridge_edition()
    try:
        imp = pipeline.run_import(
            db,
            importer_id=user.id,
            source_kind=body.source_kind,
            source_ref=body.source_ref,
            pii_profile=body.pii_profile,
            project_id=body.project_id,
            request=request,
            user=user,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_out(imp)


@router.get("/imports", response_model=list[ImportOut])
async def list_imports(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    return [_to_out(i) for i in reader.list_imports(db, include_deleted=include_deleted)]


@router.get("/imports/{import_id}/manifest")
async def get_manifest(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    imp = reader.get_import(db, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="import not found")
    manifest = reader.read_manifest(imp)
    if manifest is None:
        raise HTTPException(status_code=404, detail="manifest not available")
    return manifest


@router.get("/imports/{import_id}/structure")
async def get_structure(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    imp = reader.get_import(db, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="import not found")
    md = reader.read_structure_md(imp)
    if md is None:
        raise HTTPException(status_code=404, detail="structure not available")
    return {"import_id": import_id, "structure_md": md}


@router.get("/imports/{import_id}/command/{name}")
async def get_command(
    import_id: int,
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_bridge_edition()
    imp = reader.get_import(db, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="import not found")
    cmd = reader.get_command(imp, name)
    if cmd is None:
        raise HTTPException(status_code=404, detail="command not found")
    return cmd


@router.get("/imports/{import_id}/roundtrip")
async def roundtrip_check(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Round-trip acceptance test (success metric): reconstruct schema from the
    artifact and diff it against the live source. Returns fidelity + defects."""
    _require_bridge_edition()
    imp = reader.get_import(db, import_id)
    if imp is None:
        raise HTTPException(status_code=404, detail="import not found")
    if not imp.artifact_dir:
        raise HTTPException(status_code=409, detail="import not yet transformed")
    return roundtrip.run(db, imp).as_dict()


# --------------------------------------------------------------------------- #
# P4: AI retrieval index (Enterprise) + regeneration handoff
# --------------------------------------------------------------------------- #

class QueryRequest(BaseModel):
    text: str
    k: int = 5


class McpTokenCreate(BaseModel):
    name: str
    scope: str = "read"   # read | read_write


@router.get("/projects/{project_id}/tokens")
async def list_mcp_tokens(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Enterprise: MCP access tokens for external AI agents on this project."""
    _require_bridge_edition()
    _require_vector_edition()   # ENT-only
    return mcp_token_service.list_tokens(db, project_id)


@router.post("/projects/{project_id}/tokens")
async def create_mcp_token(
    project_id: int,
    body: McpTokenCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Mint a scoped MCP token. The plaintext is returned ONCE — store it now."""
    _require_bridge_edition()
    _require_vector_edition()
    if project_service.get(db, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    token, row = mcp_token_service.create(
        db, project_id=project_id, name=body.name, scope=body.scope, created_by=user.id)
    audit_service.create_audit_log(
        db, request, user, action="opencli_mcp_token_create", resource_type="opencli",
        resource_id=str(row.id),
        details=f"mint MCP token '{row.name}' scope={row.scope} project={project_id}",
        log_level="WARNING",
    )
    return {"id": row.id, "name": row.name, "scope": row.scope,
            "token": token, "note": "Copy now — shown only once."}


@router.delete("/tokens/{token_id}")
async def revoke_mcp_token(
    token_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Revoke an MCP token — the agent can no longer connect."""
    _require_bridge_edition()
    _require_vector_edition()
    row = mcp_token_service.revoke(db, token_id)
    if row is None:
        raise HTTPException(status_code=404, detail="token not found")
    audit_service.create_audit_log(
        db, request, user, action="opencli_mcp_token_revoke", resource_type="opencli",
        resource_id=str(token_id), details=f"revoke MCP token '{row.name}'", log_level="WARNING",
    )
    return {"ok": True, "token_id": token_id}


@router.post("/imports/{import_id}/index/rebuild")
async def rebuild_index(
    import_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Enterprise: (re)build the derived AI retrieval index from the artifacts."""
    _require_bridge_edition()
    _require_vector_edition()
    imp = _load_import(db, import_id)
    return vector.rebuild(imp)


@router.post("/imports/{import_id}/index/query")
async def query_index(
    import_id: int,
    body: QueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enterprise: semantic-ish search over the artifacts for agent RAG."""
    _require_bridge_edition()
    _require_vector_edition()
    imp = _load_import(db, import_id)
    return {"import_id": import_id, "query": body.text,
            "results": vector.query(imp, body.text, k=body.k)}


class LlmConfigIn(BaseModel):
    provider: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None   # write-only; encrypted at rest


@router.get("/llm/config")
async def get_llm_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Provider config for regeneration. Never returns the key, only has_key."""
    _require_bridge_edition()
    return regen_service.get_config(db)


@router.put("/llm/config")
async def set_llm_config(
    body: LlmConfigIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Choose the LLM provider (manual | anthropic | openai-compatible). No lock-in:
    'manual' needs nothing; 'openai' + base_url can target a local on-prem model."""
    _require_bridge_edition()
    try:
        cfg = regen_service.set_config(
            db, provider=body.provider, model=body.model,
            base_url=body.base_url, api_key=body.api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.create_audit_log(
        db, request, user, action="opencli_llm_config", resource_type="opencli",
        details=f"provider={body.provider} model={body.model or '-'} "
                f"base_url={body.base_url or '-'} key_set={bool(body.api_key)}",
        log_level="WARNING",
    )
    return cfg


class LlmModelCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    label: str
    provider: str
    model: str
    base_url: Optional[str] = None
    vault_key_id: Optional[int] = None


@router.get("/llm/models")
async def list_llm_models(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Configured AI models (multi-agent). Keys live in the Vault, not here."""
    _require_bridge_edition()
    return {
        "models": llm_models_service.list_models(db),
        # vault keys the user can pick from (คลัง API Key) — name/provider/category
        "vault_keys": [{"id": k.id, "name": k.name, "provider": k.provider,
                        "category": k.category}
                       for k in db.query(VaultKey).order_by(VaultKey.name).all()],
    }


@router.post("/llm/models")
async def create_llm_model(
    body: LlmModelCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    _require_bridge_edition()
    row = llm_models_service.create(
        db, label=body.label, provider=body.provider, model=body.model,
        base_url=body.base_url, vault_key_id=body.vault_key_id, created_by=user.id)
    audit_service.create_audit_log(
        db, request, user, action="opencli_llm_model_add", resource_type="opencli",
        resource_id=str(row.id),
        details=f"AI model '{row.label}' {row.provider}/{row.model} key={body.vault_key_id}",
        log_level="INFO")
    return {"id": row.id, "label": row.label}


@router.post("/llm/models/{model_id}/test")
async def test_llm_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    _require_bridge_edition()
    try:
        return llm_models_service.test(db, model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/llm/models/{model_id}")
async def delete_llm_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    _require_bridge_edition()
    if not llm_models_service.delete(db, model_id):
        raise HTTPException(status_code=404, detail="model not found")
    return {"ok": True}


@router.post("/llm/test")
async def test_llm(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Probe the configured provider — returns {ok, detail} for a status badge."""
    _require_bridge_edition()
    return regen_service.test_config(db)


@router.get("/imports/{import_id}/modules")
async def list_import_modules(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Modules of the imported system (grouped by table prefix) — one build step each."""
    _require_bridge_edition()
    imp = _load_import(db, import_id)
    return modules_svc.list_modules(imp)


@router.post("/imports/{import_id}/regen/module")
async def regen_module(
    import_id: int,
    body: ModuleGenRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Generate ONE module (scoped) — step-by-step / natural-language build."""
    _require_bridge_edition()
    imp = _load_import(db, import_id)
    try:
        result = regen_service.generate_module(
            db, imp, body.module, created_by=user.id, model_id=body.model_id)
    except Exception as e:   # never 500 — surface the reason so the UI can show it
        db.rollback()
        raise HTTPException(status_code=400, detail=f"module gen failed: {str(e)[:300]}")
    try:
        audit_service.create_audit_log(
            db, request, user, action="opencli_regen_module", resource_type="opencli",
            resource_id=str(import_id),
            details=f"module={body.module} provider={result['provider']} files={result['files']}",
            log_level="WARNING")
    except Exception:
        db.rollback()   # audit must never break the result
    return result


@router.post("/imports/{import_id}/regen/generate")
async def regen_generate(
    import_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Run the configured provider on the import's brief. Manual mode returns the
    brief; LLM modes return generated files + structural verification."""
    _require_bridge_edition()
    imp = _load_import(db, import_id)
    try:
        result = regen_service.generate(db, imp, created_by=user.id)
    except Exception as e:   # never 500 — surface the reason
        db.rollback()
        raise HTTPException(status_code=400, detail=f"generate failed: {str(e)[:300]}")
    audit_service.create_audit_log(
        db, request, user, action="opencli_regen", resource_type="opencli",
        resource_id=str(import_id),
        details=f"provider={result['provider']} mode={result['mode']} files={result['files']}",
        log_level="WARNING",
    )
    return result


class DeployCodeRequest(BaseModel):
    name: str


@router.post("/imports/{import_id}/merge-deploy")
async def merge_deploy(
    import_id: int,
    body: MergeDeployRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Merge every module's latest code into one app, then (optionally) deploy it
    on iVS — the whole regenerated system in one place."""
    _require_bridge_edition()
    imp = _load_import(db, import_id)
    try:
        cv = code_service.merge_modules(db, imp, created_by=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_service.create_audit_log(
        db, request, user, action="opencli_merge", resource_type="opencli",
        resource_id=str(import_id),
        details=f"merged modules → code v{cv.version} ({cv.files_count} files)",
        log_level="WARNING",
    )
    result = {"merged_code_id": cv.id, "version": cv.version,
              "files": cv.files_count, "deploy": None}
    if body.deploy:
        try:
            result["deploy"] = await code_service.deploy(
                db, cv, name=body.name, user=user, request=request)
        except Exception as e:   # Docker down etc — merge still succeeded
            result["deploy_error"] = str(e)[:300]
    return result


def _load_code(db: Session, code_id: int) -> OpenCliCodeVersion:
    cv = db.get(OpenCliCodeVersion, code_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="code version not found")
    return cv


@router.get("/imports/{import_id}/code")
async def list_import_code(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Code versions generated from this import (history, newest first)."""
    _require_bridge_edition()
    return code_service.list_versions(db, import_id=import_id)


@router.get("/imports/{import_id}/gen-attempts")
async def import_gen_attempts(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Module-generation attempt history (errors + successes) for an import."""
    _require_bridge_edition()
    return regen_service.list_attempts(db, import_id=import_id)


@router.get("/imports/{import_id}/deploys")
async def import_deploys(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge+Deploy history for an import."""
    _require_bridge_edition()
    return code_service.list_deploys(db, import_id=import_id)


@router.post("/code/{code_id}/deploy")
async def deploy_code(
    code_id: int,
    body: DeployCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Deploy a code version as an IVS app (reuses the deploy path; needs Docker)."""
    _require_bridge_edition()
    cv = _load_code(db, code_id)
    try:
        return await code_service.deploy(db, cv, name=body.name, user=user, request=request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/code/{code_id}/export")
async def export_code(
    code_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the code version as a .zip."""
    _require_bridge_edition()
    cv = _load_code(db, code_id)
    try:
        filename, data = code_service.export_zip(cv)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/code/{code_id}")
async def delete_code(
    code_id: int,
    body: DeleteRequest,   # password + reason, same as import delete
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Delete a code version — password re-auth + audit (iVS destructive standard).
    Row is kept as a deletion-marked history entry."""
    _require_bridge_edition()
    if not verify_password(body.password, user.password_hash):
        logger.warning("opencli code delete: bad password for user %s", user.id)
        raise HTTPException(status_code=403, detail="Invalid credentials.")
    cv = _load_code(db, code_id)
    code_service.delete_version(db, cv, deleted_by=user.id, reason=body.reason,
                                request=request, user=user)
    return {"ok": True, "code_id": code_id}


@router.get("/imports/{import_id}/regen/brief")
async def regen_brief(
    import_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Self-contained generation brief for an external AI agent (regeneration)."""
    _require_bridge_edition()
    imp = _load_import(db, import_id)
    return regen.build_brief(imp)


@router.delete("/imports/{import_id}", response_model=DeletionOut)
async def delete_import(
    import_id: int,
    body: DeleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.DEVELOPER)),
):
    """Destructive — password re-auth required; records deletion history (Stage 5)."""
    _require_bridge_edition()
    if not verify_password(body.password, user.password_hash):
        # generic 403, logged, like retention purge
        logger.warning("opencli delete: bad password for user %s", user.id)
        raise HTTPException(status_code=403, detail="Invalid credentials.")
    try:
        deletion = pipeline.delete_import(
            db, import_id=import_id, deleted_by=user.id,
            reason=body.reason, request=request, user=user,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return DeletionOut.model_validate(deletion)


@router.get("/deletions", response_model=list[DeletionOut])
async def list_deletions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Deletion history — survives removal of the import row."""
    _require_bridge_edition()
    rows = (db.query(OpenCliImportDeletion)
            .order_by(OpenCliImportDeletion.deleted_at.desc()).all())
    return [DeletionOut.model_validate(r) for r in rows]
