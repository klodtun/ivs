"""AI retrieval index (P4, Enterprise) — chunk Bridge artifacts for agent RAG.

Per the architecture: the index is DERIVED and REBUILDABLE from the artifact
files, never the source of truth. So a future AI-DB swap = re-chunk + re-index,
zero migration.

This module ships:
  * `chunk_import()` — artifacts (manifest + structure.md) -> stable-id chunks
  * `VectorIndex` protocol — pluggable backend
  * `KeywordIndex` — default backend, no external deps (lexical scoring). ENT can
    register a pgvector / Qdrant backend that embeds the same chunks.
  * `rebuild()` / `query()` — build from files, search.

Chunk ids are stable (`<import_id>:<kind>:<ref>`) so re-indexing is idempotent.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from app.models import OpenCliImport
from . import reader

_WORD = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


@dataclass
class Chunk:
    id: str                       # stable: "<import_id>:<kind>:<ref>"
    import_id: int
    kind: str                     # "command" | "entity" | "overview"
    ref: str                      # command name / entity / "system"
    text: str
    metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Chunking — derive chunks from the artifact files
# --------------------------------------------------------------------------- #

def chunk_import(imp: OpenCliImport) -> list[Chunk]:
    manifest = reader.read_manifest(imp) or []
    md = reader.read_structure_md(imp) or ""
    site = manifest[0].get("site") if manifest else str(imp.id)
    chunks: list[Chunk] = []

    # overview chunk
    chunks.append(Chunk(
        id=f"{imp.id}:overview:system",
        import_id=imp.id, kind="overview", ref="system",
        text=f"System {site}. {len(manifest)} OpenCLI commands. "
             f"PII profile {imp.pii_profile.value}. Source {imp.source_kind}.",
        metadata={"site": site, "command_count": len(manifest)},
    ))

    # one chunk per command
    for cmd in manifest:
        name = cmd.get("name", "?")
        cols = ", ".join(cmd.get("columns", []))
        chunks.append(Chunk(
            id=f"{imp.id}:command:{name}",
            import_id=imp.id, kind="command", ref=name,
            text=f"Command {name} ({cmd.get('access')}) on {cmd.get('sourceFile')}. "
                 f"strategy {cmd.get('strategy')}. columns: {cols}.",
            metadata={"access": cmd.get("access"), "sourceFile": cmd.get("sourceFile")},
        ))

    # one chunk per entity section of structure.md (split on "### ")
    for section in md.split("\n### ")[1:]:
        head = section.splitlines()[0].strip()
        ref = head.split("`")[1] if "`" in head else head[:40]
        chunks.append(Chunk(
            id=f"{imp.id}:entity:{ref}",
            import_id=imp.id, kind="entity", ref=ref,
            text="### " + section.strip(),
            metadata={},
        ))
    return chunks


# --------------------------------------------------------------------------- #
# Pluggable backend
# --------------------------------------------------------------------------- #

@runtime_checkable
class VectorIndex(Protocol):
    backend: str

    def upsert(self, chunks: list[Chunk]) -> None: ...
    def query(self, text: str, k: int = 5) -> list[dict]: ...
    def save(self, path: str) -> None: ...
    def clear_import(self, import_id: int) -> None: ...


class KeywordIndex:
    """Dependency-free default backend: TF-IDF-ish lexical scoring.

    Good enough to prove the pipeline + let an agent retrieve relevant commands.
    ENT swaps this for an embedding backend using the SAME chunks."""
    backend = "keyword"

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._tf: dict[str, Counter] = {}

    def upsert(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self._chunks[c.id] = c
            self._tf[c.id] = Counter(_tokens(c.text))

    def clear_import(self, import_id: int) -> None:
        for cid in [c for c in self._chunks if self._chunks[c].import_id == import_id]:
            self._chunks.pop(cid, None)
            self._tf.pop(cid, None)

    def _idf(self) -> dict[str, float]:
        n = len(self._chunks) or 1
        df: Counter = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        return {term: math.log((n + 1) / (c + 1)) + 1 for term, c in df.items()}

    def query(self, text: str, k: int = 5) -> list[dict]:
        idf = self._idf()
        q = _tokens(text)
        scored: list[tuple[float, Chunk]] = []
        for cid, tf in self._tf.items():
            score = sum(tf.get(term, 0) * idf.get(term, 0) for term in q)
            if score > 0:
                scored.append((score, self._chunks[cid]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": c.id, "kind": c.kind, "ref": c.ref, "score": round(s, 3),
             "text": c.text, "metadata": c.metadata}
            for s, c in scored[:k]
        ]

    def save(self, path: str) -> None:
        data = {"backend": self.backend,
                "chunks": [vars(c) for c in self._chunks.values()]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "KeywordIndex":
        idx = cls()
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            idx.upsert([Chunk(**c) for c in data.get("chunks", [])])
        return idx


# Backend registry — ENT registers "pgvector" / "qdrant" here.
_BACKENDS = {"keyword": KeywordIndex}


def make_index(backend: str = "keyword") -> VectorIndex:
    try:
        return _BACKENDS[backend]()
    except KeyError:
        raise ValueError(f"unknown vector backend: {backend!r} (have {list(_BACKENDS)})")


# --------------------------------------------------------------------------- #
# High-level ops
# --------------------------------------------------------------------------- #

def _index_path(imp: OpenCliImport) -> Optional[str]:
    return os.path.join(imp.artifact_dir, "index.json") if imp.artifact_dir else None


def rebuild(imp: OpenCliImport, backend: str = "keyword") -> dict:
    """Re-chunk the artifacts and (re)build the derived index file. Idempotent."""
    idx = make_index(backend)
    chunks = chunk_import(imp)
    idx.upsert(chunks)
    path = _index_path(imp)
    if path:
        idx.save(path)
    return {"import_id": imp.id, "backend": backend,
            "chunks": len(chunks), "index_path": path}


def query(imp: OpenCliImport, text: str, k: int = 5, backend: str = "keyword") -> list[dict]:
    """Load the derived index (rebuild on the fly if missing) and search."""
    path = _index_path(imp)
    if backend == "keyword" and path and os.path.isfile(path):
        idx: VectorIndex = KeywordIndex.load(path)
    else:
        idx = make_index(backend)
        idx.upsert(chunk_import(imp))
    return idx.query(text, k=k)
