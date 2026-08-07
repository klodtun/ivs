"""Project-level operations (P16) — treat one project/app as the unit of work.

A project groups several imports (each a source version). This builds a COMBINED
manifest (union of all the project's transformed imports) and a lightweight
import-like wrapper so the existing per-import logic (modules / regen / merge /
structure) can run at project scope — without changing any per-import code path.

Additive by design: per-import endpoints are untouched, so they remain a fallback
if anything here misbehaves.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    OpenCliImport,
    OpenCliImportStatus,
    OpenCliPiiProfile,
    OpenCliProject,
)
from . import reader
from .pipeline import _artifact_root


@dataclass
class CombinedImport:
    """Duck-types the parts of OpenCliImport that modules/regen/reader use:
    artifact_dir, project_id, pii_profile, source_kind, source_ref, id."""
    project_id: int
    artifact_dir: str
    pii_profile: OpenCliPiiProfile
    source_ref: str
    command_count: int
    id: Optional[int] = None          # no real import row → import_id NULL on code versions
    source_kind: str = "project"


def project_imports(db: Session, project_id: int) -> list[OpenCliImport]:
    return (db.query(OpenCliImport)
            .filter(OpenCliImport.project_id == project_id,
                    OpenCliImport.status == OpenCliImportStatus.TRANSFORMED)
            .order_by(OpenCliImport.created_at.asc()).all())


def build_combined(db: Session, project: OpenCliProject) -> CombinedImport:
    """Union every transformed import's manifest into one, written to a project
    dir. Reused by the module/regen/merge/structure project endpoints."""
    imps = project_imports(db, project.id)
    if not imps:
        raise ValueError("project has no transformed imports yet")

    manifest: list[dict] = []
    seen: set[str] = set()
    md_parts: list[str] = [f"# {project.name} — combined structure", ""]
    for imp in imps:
        for cmd in (reader.read_manifest(imp) or []):
            key = cmd.get("sourceFile") or cmd.get("name")
            if key and key not in seen:
                seen.add(key)
                # re-tag site to the project so the manifest is coherent
                c = dict(cmd); c["site"] = project.slug
                manifest.append(c)
        smd = reader.read_structure_md(imp)
        if smd:
            md_parts.append(f"## from import #{imp.id} ({imp.source_kind})")
            md_parts.append(smd)

    d = Path(str(_artifact_root())) / "_projects" / str(project.id) / "combined"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cli-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d / "structure.md").write_text("\n\n".join(md_parts), encoding="utf-8")

    return CombinedImport(
        project_id=project.id, artifact_dir=str(d),
        pii_profile=imps[0].pii_profile, source_ref=project.name,
        command_count=len(manifest),
    )
