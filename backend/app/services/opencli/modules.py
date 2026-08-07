"""Module-scoped regeneration (P14) — build an app one module at a time.

A whole legacy app is too big to generate in one call. This groups the OpenCLI
commands into modules (by table-name prefix, e.g. bill1/bill2/bill3 → "bill") so
the operator can generate/extend one module per step (easy to steer in natural
language) and small models can handle each scoped chunk. Sets the foundation for
multi-agent generation (fan modules out to several AIs later).
"""
from __future__ import annotations

import re
from typing import Optional

from . import reader, regen


def _module_of(table: str) -> str:
    """Group key for a table: first token, trailing digits stripped.
    customer_location→customer, bill3→bill, sale2→sale."""
    head = table.split("_")[0]
    return re.sub(r"\d+$", "", head) or head


def _prefix_modules(imp) -> list[dict]:
    """Baseline grouping by table-name prefix (the original P14 heuristic)."""
    manifest = reader.read_manifest(imp) or []
    groups: dict[str, list[str]] = {}
    for cmd in manifest:
        src = cmd.get("sourceFile", "")
        if src.startswith("table:"):
            table = src[len("table:"):]
            groups.setdefault(_module_of(table), []).append(table)
    return [
        {"module": m, "tables": sorted(set(t)), "commands": len(t)}
        for m, t in sorted(groups.items())
    ]


def list_modules(imp) -> list[dict]:
    """Modules for an import's manifest, with their tables + command count.

    Prefers relationship-based clustering (P17, module_graph) which groups tables by
    implied foreign keys, not just name prefix. Falls back to the prefix heuristic
    when there is no relational signal — so this is never worse than P14."""
    try:
        from . import module_graph
        clustered = module_graph.graph_modules(imp)
        if clustered:
            return clustered
    except Exception:
        pass  # any failure → safe fallback below
    return _prefix_modules(imp)


def build_module_brief(imp, module: str) -> dict:
    """Full brief, but the manifest is filtered to this module's tables. The
    legacy code map is kept whole for context; the target module is named."""
    brief = regen.build_brief(imp)
    tables = {t for grp in list_modules(imp) if grp["module"] == module for t in grp["tables"]}
    brief["target_module"] = module
    brief["manifest"] = [
        c for c in brief["manifest"]
        if c.get("sourceFile", "").startswith("table:")
        and c["sourceFile"][len("table:"):] in tables
    ]
    brief["instruction"] = (
        f"Generate ONLY the '{module}' module (tables: {', '.join(sorted(tables))}). "
        f"Produce a runnable slice for this module that fits the target app layout. "
        f"Other modules are generated separately."
    )
    return brief
