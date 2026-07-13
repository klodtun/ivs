"""Read-side helpers for OpenCLI Bridge artifacts.

Shared by the router (HTTP) and the MCP server (stdio). Reads the metadata rows
and the on-disk manifest/markdown files. No mutation.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from sqlalchemy.orm import Session

from app.models import OpenCliImport, OpenCliImportStatus


def list_imports(db: Session, include_deleted: bool = False) -> list[OpenCliImport]:
    q = db.query(OpenCliImport)
    if not include_deleted:
        q = q.filter(OpenCliImport.status != OpenCliImportStatus.DELETED)
    return q.order_by(OpenCliImport.created_at.desc()).all()


def get_import(db: Session, import_id: int) -> Optional[OpenCliImport]:
    return db.get(OpenCliImport, import_id)


def _artifact_path(imp: OpenCliImport, filename: str) -> Optional[str]:
    if not imp.artifact_dir:
        return None
    path = os.path.join(imp.artifact_dir, filename)
    return path if os.path.isfile(path) else None


def read_manifest(imp: OpenCliImport) -> Optional[list[dict]]:
    path = _artifact_path(imp, "cli-manifest.json")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_structure_md(imp: OpenCliImport) -> Optional[str]:
    path = _artifact_path(imp, "structure.md")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def get_command(imp: OpenCliImport, name: str) -> Optional[dict]:
    manifest = read_manifest(imp)
    if not manifest:
        return None
    for cmd in manifest:
        if cmd.get("name") == name:
            return cmd
    return None
