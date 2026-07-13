"""OpenCLI Bridge pipeline — orchestrates stages 1,2,3,5.

  1 Import    : probe + SHA-256 the raw source bytes (read-only, never persisted)
  2 PII Filter: applied inside transform (EXCLUDE drops / ANONYMIZE redacts)
  3 Transform : Structure -> cli-manifest.json + structure.md (files)
  5 History   : OpenCliImport row + audit log; git-per-import versioning

Stage 4 (MCP publish) and the router/UI are P2.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    OpenCliImport,
    OpenCliImportDeletion,
    OpenCliImportStatus,
    OpenCliPiiProfile,
)
from app.services import audit_service

from .connectors.base import SourceConnector
from .connectors.sqlite_conn import SqliteConnector
from .connectors.rest_conn import RestConnector
from .connectors.sqlalchemy_conn import SqlAlchemyConnector
from .connectors.sqldump_conn import SqlDumpConnector
from . import transform

_CHUNK = 1 << 20  # 1 MiB

_sql = SqlAlchemyConnector()   # one connector, many dialects
_dump = SqlDumpConnector()
_CONNECTORS: dict[str, SourceConnector] = {
    "sqlite": SqliteConnector(),
    "rest": RestConnector(),
    "postgres": _sql,
    "mysql": _sql,
    "mssql": _sql,
    "oracle": _sql,
    "sql": _sql,          # generic — source_ref is a full SQLAlchemy URL
    "sqldump": _dump,     # a .sql export file (schema-only, no data read)
}
_SQL_KINDS = {"postgres", "mysql", "mssql", "oracle", "sql"}


def _artifact_root() -> Path:
    override = os.environ.get("BRIDGE_ARTIFACT_ROOT")
    if override:
        return Path(override)
    # .../IVS/backend/app/services/opencli/pipeline.py -> parents[4] == IVS
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "deployed_apps" / "_bridge"


def get_connector(kind: str) -> SourceConnector:
    try:
        return _CONNECTORS[kind]
    except KeyError:
        raise ValueError(f"unsupported source_kind: {kind!r} (have {list(_CONNECTORS)})")


def _sha256_file(path: str) -> tuple[str, int]:
    """Stream the raw source through SHA-256. Bytes are discarded, never stored."""
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _commit_artifacts(art_dir: Path, message: str) -> None:
    """git-per-import: init on first transform, commit every re-transform."""
    if not (art_dir / ".git").exists():
        _git(art_dir, "init", "-q")
        _git(art_dir, "config", "user.email", "bridge@ivs.local")
        _git(art_dir, "config", "user.name", "IVS OpenCLI Bridge")
    _git(art_dir, "add", "-A")
    # allow empty so a re-transform with no change still records a commit point
    _git(art_dir, "commit", "-q", "--allow-empty", "-m", message)


def run_import(
    db: Session,
    *,
    importer_id: Optional[int],
    source_kind: str,
    source_ref: str,
    pii_profile: OpenCliPiiProfile,
    project_id: Optional[int] = None,
    request=None,
    user=None,
) -> OpenCliImport:
    """Full stage 1->2->3->5. Returns the persisted OpenCliImport (TRANSFORMED)."""
    connector = get_connector(source_kind)

    # --- Stage 1: import (read-only) + hash raw bytes ---------------------
    meta = connector.probe(source_ref)
    if source_kind == "sqlite":
        sha256_raw, size = _sha256_file(source_ref)
    elif source_kind == "rest":
        raw = connector.raw_bytes(source_ref)  # the openapi.json document
        sha256_raw, size = hashlib.sha256(raw).hexdigest(), len(raw)
    elif source_kind in _SQL_KINDS:
        # live DB: deterministic schema fingerprint + row count (no data copied)
        sha256_raw, size = connector.fingerprint(source_ref)
    elif source_kind == "sqldump":
        # the whole .sql file is hashed → importer can sha256sum + verify (Row1)
        sha256_raw, size = connector.file_sha256(source_ref)
    else:
        raise ValueError(f"hashing not implemented for kind {source_kind!r}")

    # metadata row first, to mint the id used for the artifact dir ----------
    imp = OpenCliImport(
        project_id=project_id,
        importer_id=importer_id,
        source_kind=source_kind,
        source_ref=source_ref,
        source_bytes=size,
        sha256_raw=sha256_raw,
        pii_profile=pii_profile,
        status=OpenCliImportStatus.PENDING,
    )
    db.add(imp)
    db.flush()  # assigns imp.id without committing

    # --- Stage 2+3: PII filter + transform to artifacts -------------------
    structure = connector.structure(source_ref)
    manifest = transform.build_manifest(structure, pii_profile)
    md = transform.build_structure_md(structure, pii_profile)
    manifest_text = transform.manifest_json(manifest)
    manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    art_dir = _artifact_root() / str(imp.id)
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "cli-manifest.json").write_text(manifest_text, encoding="utf-8")
    (art_dir / "structure.md").write_text(md, encoding="utf-8")

    _commit_artifacts(
        art_dir,
        f"transform import #{imp.id} ({structure.site}, "
        f"{len(manifest)} cmds, pii={pii_profile.value})",
    )

    # --- Stage 5: finalize history row + audit ----------------------------
    imp.artifact_dir = str(art_dir)
    imp.manifest_sha = manifest_sha
    imp.command_count = len(manifest)
    imp.status = OpenCliImportStatus.TRANSFORMED
    db.add(imp)

    if request is not None:
        audit_service.create_audit_log(
            db, request, user,
            action="opencli_import",
            resource_type="opencli",
            resource_id=str(imp.id),
            details=(f"import {source_kind}:{source_ref} sha256={sha256_raw[:12]}… "
                     f"cmds={len(manifest)} pii={pii_profile.value}"),
            log_level="WARNING",
        )
    db.commit()
    db.refresh(imp)
    return imp


def delete_import(
    db: Session,
    *,
    import_id: int,
    deleted_by: Optional[int],
    reason: Optional[str] = None,
    request=None,
    user=None,
) -> OpenCliImportDeletion:
    """Soft-delete: record deletion history (survives row removal), audit WARNING."""
    imp = db.get(OpenCliImport, import_id)
    if imp is None:
        raise ValueError(f"import #{import_id} not found")

    deletion = OpenCliImportDeletion(
        import_id=imp.id,
        deleted_by=deleted_by,
        reason=reason,
        sha256_raw=imp.sha256_raw,  # preserved even after status flip
    )
    db.add(deletion)
    imp.status = OpenCliImportStatus.DELETED
    db.add(imp)

    if request is not None:
        audit_service.create_audit_log(
            db, request, user,
            action="opencli_import_delete",
            resource_type="opencli",
            resource_id=str(imp.id),
            details=f"delete import #{imp.id} sha256={imp.sha256_raw[:12]}… reason={reason or '-'}",
            log_level="WARNING",
        )
    db.commit()
    db.refresh(deletion)
    return deletion
