"""Project/App service (P7) — group imports, code versions, and MCP tokens.

A project is the unit multiple people collaborate on over time: they add imports
(each a version of the source), generate code from them, deploy, and connect
external agents. Imports/code/tokens all hang off a project.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    OpenCliProject,
    OpenCliImport,
    OpenCliImportStatus,
    OpenCliCodeVersion,
    OpenCliCodeStatus,
)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def _unique_slug(db: Session, base: str) -> str:
    slug, i = base, 1
    while db.query(OpenCliProject).filter(OpenCliProject.slug == slug).first():
        i += 1
        slug = f"{base}-{i}"
    return slug


def create(db: Session, *, name: str, description: Optional[str], owner_id: Optional[int]) -> OpenCliProject:
    p = OpenCliProject(
        name=name.strip() or "Untitled",
        slug=_unique_slug(db, _slugify(name)),
        description=description,
        owner_id=owner_id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def get(db: Session, project_id: int) -> Optional[OpenCliProject]:
    return db.get(OpenCliProject, project_id)


def list_projects(db: Session) -> list[dict]:
    """List projects with import + code-version counts for the dashboard."""
    out = []
    for p in db.query(OpenCliProject).order_by(OpenCliProject.created_at.desc()).all():
        imports = (db.query(OpenCliImport)
                   .filter(OpenCliImport.project_id == p.id,
                           OpenCliImport.status != OpenCliImportStatus.DELETED).count())
        codes = (db.query(OpenCliCodeVersion)
                 .filter(OpenCliCodeVersion.project_id == p.id,
                         OpenCliCodeVersion.status != OpenCliCodeStatus.DELETED).count())
        out.append({
            "id": p.id, "name": p.name, "slug": p.slug,
            "description": p.description or "", "owner_id": p.owner_id,
            "imports": imports, "code_versions": codes,
            "created_at": p.created_at.isoformat(),
        })
    return out
