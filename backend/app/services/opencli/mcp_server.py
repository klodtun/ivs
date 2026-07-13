"""OpenCLI Bridge — MCP server (stage 4).

Exposes published imports to an external AI agent (Claude Code / Cursor) so it
can read the OpenCLI manifest + structure and regenerate/extend the system in
natural language.

Transport: MCP stdio (newline-delimited JSON-RPC 2.0). No third-party deps, so
any agent can mount it. Run:

    cd backend && python -m app.services.opencli.mcp_server

Agent config (Claude Code .mcp.json):

    {"mcpServers": {"ivs-opencli": {
        "command": "bash",
        "args": ["-c", "cd /path/to/IVS/backend && source venv/bin/activate && python -m app.services.opencli.mcp_server"]
    }}}

Read-only: the server never writes to the DB or the source.
"""
from __future__ import annotations

import json
import sys

from app.database import SessionLocal
from app.services.opencli import reader

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "ivs-opencli-bridge", "version": "0.1.0"}

TOOLS = [
    {
        "name": "list_imports",
        "description": "List published OpenCLI Bridge imports (id, site, status, command_count).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_manifest",
        "description": "Return the cli-manifest.json (array of OpenCLI commands) for an import.",
        "inputSchema": {
            "type": "object",
            "properties": {"import_id": {"type": "integer"}},
            "required": ["import_id"], "additionalProperties": False,
        },
    },
    {
        "name": "get_structure",
        "description": "Return the structure.md (entities/columns/PII notes) for an import.",
        "inputSchema": {
            "type": "object",
            "properties": {"import_id": {"type": "integer"}},
            "required": ["import_id"], "additionalProperties": False,
        },
    },
    {
        "name": "get_command",
        "description": "Return one OpenCLI command's full spec by import_id + command name.",
        "inputSchema": {
            "type": "object",
            "properties": {"import_id": {"type": "integer"}, "name": {"type": "string"}},
            "required": ["import_id", "name"], "additionalProperties": False,
        },
    },
]


def _text(obj) -> dict:
    body = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": body}]}


def _err(msg: str) -> dict:
    return {"content": [{"type": "text", "text": msg}], "isError": True}


def _call_tool(name: str, args: dict) -> dict:
    db = SessionLocal()
    try:
        if name == "list_imports":
            rows = reader.list_imports(db)
            return _text([
                {"id": r.id,
                 "site": (reader.read_manifest(r) or [{}])[0].get("site") if r.artifact_dir else None,
                 "status": r.status.value,
                 "command_count": r.command_count,
                 "created_at": r.created_at.isoformat()}
                for r in rows
            ])

        if name == "get_manifest":
            imp = reader.get_import(db, int(args["import_id"]))
            if imp is None:
                return _err("import not found")
            m = reader.read_manifest(imp)
            return _text(m) if m is not None else _err("manifest not available")

        if name == "get_structure":
            imp = reader.get_import(db, int(args["import_id"]))
            if imp is None:
                return _err("import not found")
            md = reader.read_structure_md(imp)
            return _text(md) if md is not None else _err("structure not available")

        if name == "get_command":
            imp = reader.get_import(db, int(args["import_id"]))
            if imp is None:
                return _err("import not found")
            cmd = reader.get_command(imp, args["name"])
            return _text(cmd) if cmd is not None else _err("command not found")

        return _err(f"unknown tool: {name}")
    finally:
        db.close()


def _handle(msg: dict):
    """Return a JSON-RPC response dict, or None for notifications."""
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        result = _call_tool(params.get("name"), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}

    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
