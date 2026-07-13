"""REST source connector (P3, experimental) — introspect an OpenAPI endpoint.

Reads `<base>/openapi.json` (FastAPI apps, incl. deployed ivs-<slug> containers,
expose it) and maps each operation to an OpenCLI command. Read-only: only GET
operations become `read` commands; write ops are surfaced as `write` (an agent
decides whether to call them). No request bodies are executed here.

`stream()` is intentionally not implemented for P3 — structure introspection is
enough to emit the manifest. Hashing (stage 1) uses the raw openapi.json bytes.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Iterator

from .base import Column, Entity, Record, SourceConnector, SourceMeta, Structure

_TIMEOUT = 10
_METHOD_ACCESS = {"get": "read", "head": "read", "options": "read"}


def _slug_from_url(url: str) -> str:
    host = url.split("://", 1)[-1].split("/", 1)[0]
    return host.replace(":", "-").replace(".", "-") or "rest"


def _fetch(url: str) -> bytes:
    # nosec: operator-supplied URL, read-only GET, short timeout
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310
        return resp.read()


def _openapi_url(ref: str) -> str:
    ref = ref.rstrip("/")
    return ref if ref.endswith(".json") else f"{ref}/openapi.json"


class RestConnector:
    strategy = "intercept"

    def _spec(self, ref: str) -> dict:
        return json.loads(_fetch(_openapi_url(ref)))

    def probe(self, ref: str) -> SourceMeta:
        raw = _fetch(_openapi_url(ref))
        return SourceMeta(kind="rest", ref=ref, size_bytes=len(raw))

    def raw_bytes(self, ref: str) -> bytes:
        """Stage-1 hash input: the openapi.json document."""
        return _fetch(_openapi_url(ref))

    def structure(self, ref: str) -> Structure:
        spec = self._spec(ref)
        paths = spec.get("paths", {}) or {}
        entities: list[Entity] = []
        for path, ops in paths.items():
            for method, op in (ops or {}).items():
                m = method.lower()
                if m not in ("get", "post", "put", "patch", "delete", "head"):
                    continue
                access = _METHOD_ACCESS.get(m, "write")
                name = op.get("operationId") or f"{m}-{path.strip('/').replace('/', '-') or 'root'}"
                # params become columns (agent-facing input surface)
                cols = [
                    Column(name=p.get("name", "?"),
                           type=str((p.get("schema") or {}).get("type", "str")),
                           is_pii=False)
                    for p in (op.get("parameters") or [])
                ]
                entities.append(Entity(
                    name=name, columns=cols, access=access,
                    source_ref=f"{m.upper()} {path}",
                ))
        return Structure(site=_slug_from_url(ref), entities=entities)

    def stream(self, ref: str) -> Iterator[Record]:
        raise NotImplementedError(
            "RestConnector.stream is not implemented (P3 introspection-only)."
        )


_: SourceConnector = RestConnector()
