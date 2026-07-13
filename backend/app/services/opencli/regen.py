"""Regeneration handoff (P4) — close the behavioral round-trip loop.

The bridge does NOT generate code (IVS deploy path only *runs* a prebuilt .zip).
An external AI agent (Claude Code via the MCP server) writes the code. This module:

  * `build_brief()` — a self-contained generation brief the agent consumes:
    manifest + structure + target zip layout + acceptance criteria. Everything the
    agent needs to regenerate the system, in one payload.
  * `verify_candidate()` — validate the agent's produced app dir against IVS's own
    deploy-time structure check, so a bad regeneration is rejected before deploy.

Flow:  bridge artifacts ─▶ build_brief ─▶ external agent writes app/ ─▶
        verify_candidate ─▶ (ok) POST /api/apps runs it ─▶ compare behavior.
"""
from __future__ import annotations

from app.models import OpenCliImport
from . import reader


def build_brief(imp: OpenCliImport) -> dict:
    """Everything an external agent needs to regenerate the system from artifacts.
    Includes the legacy code map (the "โค้ดเดิม" input) when the project has one —
    so the AI rebuilds a faithful working replacement, not just the DB schema."""
    from . import code_analyzer  # lazy

    manifest = reader.read_manifest(imp) or []
    structure_md = reader.read_structure_md(imp) or ""
    site = manifest[0].get("site") if manifest else str(imp.id)
    code_map = code_analyzer.read_project_map(imp.project_id) if imp.project_id else None

    return {
        "import_id": imp.id,
        "project_id": imp.project_id,
        "site": site,
        "source_kind": imp.source_kind,
        "pii_profile": imp.pii_profile.value,
        "manifest": manifest,
        "structure_md": structure_md,
        "legacy_code_map": code_map,   # None if no code attached to the project
        "has_legacy_code": code_map is not None,
        "target_zip_layout": {
            "note": "Produce a .zip whose extracted root IVS deploy accepts.",
            "fullstack": ["backend/main.py (FastAPI)", "backend/requirements.txt",
                          "frontend/package.json", "frontend/dist/ (prebuilt)",
                          "Dockerfile (optional — IVS generates one)"],
            "python":    ["main.py or app.py", "requirements.txt"],
            "static":    ["index.html"],
            "exclude":   ["node_modules", "venv/.venv", ".git"],
        },
        "acceptance": {
            "structural": "verify_candidate must return issues == [].",
            "round_trip": "re-importing the regenerated system must reproduce the "
                          "same non-PII tables/columns (fidelity == 1.0).",
        },
        "mcp": {
            "server": "ivs-opencli",
            "tools": ["list_imports", "get_manifest", "get_structure", "get_command"],
        },
    }


def verify_candidate(extracted_dir: str) -> dict:
    """Run the agent's produced app dir through IVS's deploy-time validation.

    Reuses the exact check `POST /api/apps` uses, so a regeneration that would
    fail to deploy is caught here. Lazy import avoids a router<->service cycle."""
    from app.routers.apps import _validate_zip_structure  # lazy: avoid import cycle

    result = _validate_zip_structure(extracted_dir)
    issues = result.get("issues", [])
    return {
        "app_type": result.get("app_type"),
        "issues": issues,
        "warnings": result.get("warnings", []),
        "ok": len(issues) == 0,
    }
