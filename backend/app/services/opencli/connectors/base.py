"""SourceConnector interface + shared record/structure types.

A connector READS a legacy source. It must never write to or mutate the source,
and must never persist the data it reads — it only yields records in-memory and
describes structure. The pipeline hashes the raw stream and discards it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol, runtime_checkable


@dataclass
class SourceMeta:
    """Cheap probe result — size + kind, gathered without reading all data."""
    kind: str                 # "sqlite" | "rest" | "file"
    ref: str                  # path or url (reference only, no data)
    size_bytes: int = 0


@dataclass
class Column:
    name: str
    type: str = "str"         # str | int | float | bool | bytes
    is_pii: bool = False      # flagged by name heuristic; filter decides action


@dataclass
class Entity:
    """One table / endpoint / file — becomes one OpenCLI command."""
    name: str
    columns: list[Column] = field(default_factory=list)
    access: str = "read"      # read | write
    source_ref: str = ""      # e.g. "table:customers"


@dataclass
class Structure:
    """The whole source's shape — drives manifest + structure.md generation."""
    site: str                 # system id (slug)
    entities: list[Entity] = field(default_factory=list)


@dataclass
class Record:
    """One row / item. `values` maps column name -> raw value (in-memory only)."""
    entity: str
    values: dict


@runtime_checkable
class SourceConnector(Protocol):
    strategy: str             # OpenCLI strategy: local | cookie | public | intercept | ui

    def probe(self, ref: str) -> SourceMeta:
        """Return size/kind without reading the payload."""
        ...

    def structure(self, ref: str) -> Structure:
        """Introspect schema/shape. No row data leaves this call."""
        ...

    def stream(self, ref: str) -> Iterator[Record]:
        """Yield records one at a time. Caller must NOT persist raw values."""
        ...
