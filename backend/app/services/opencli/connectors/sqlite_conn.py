"""SQLite source connector (P1) — read schema + rows of a .db file.

Opens the file READ-ONLY (immutable URI) so the legacy DB is never mutated.
Rows are streamed and never written anywhere by this module.
"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Iterator

from .base import Column, Entity, Record, SourceConnector, SourceMeta, Structure

# Column-name heuristic for PII flagging (regex, P1). ML classifier = ENT (P3).
_PII_NAME = re.compile(
    r"(email|e_mail|mail|phone|tel|mobile|passport|national_id|citizen|"
    r"thai_id|ssn|card|credit|cvv|address|addr|dob|birth|firstname|lastname|"
    r"fullname|username|ip_addr|ip_address|password|passwd|token|secret)",
    re.IGNORECASE,
)

_SQLITE_TO_KIND = {
    "INTEGER": "int", "INT": "int", "REAL": "float", "FLOAT": "float",
    "NUMERIC": "float", "BOOLEAN": "bool", "BLOB": "bytes",
}


def _map_type(sql_type: str) -> str:
    base = (sql_type or "").upper().split("(")[0].strip()
    return _SQLITE_TO_KIND.get(base, "str")


def _slug(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "legacy"


def _connect_ro(path: str) -> sqlite3.Connection:
    # immutable=1 => read-only, no locks, cannot mutate the source file.
    uri = f"file:{os.path.abspath(path)}?immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class SqliteConnector:
    strategy = "local"

    def probe(self, ref: str) -> SourceMeta:
        if not os.path.isfile(ref):
            raise FileNotFoundError(f"sqlite source not found: {ref}")
        return SourceMeta(kind="sqlite", ref=ref, size_bytes=os.path.getsize(ref))

    def _tables(self, conn: sqlite3.Connection) -> list[str]:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]

    def structure(self, ref: str) -> Structure:
        conn = _connect_ro(ref)
        try:
            entities: list[Entity] = []
            for table in self._tables(conn):
                cols = []
                for c in conn.execute(f'PRAGMA table_info("{table}")').fetchall():
                    cols.append(Column(
                        name=c["name"],
                        type=_map_type(c["type"]),
                        is_pii=bool(_PII_NAME.search(c["name"])),
                    ))
                entities.append(Entity(
                    name=f"list-{table}",
                    columns=cols,
                    access="read",
                    source_ref=f"table:{table}",
                ))
            return Structure(site=_slug(ref), entities=entities)
        finally:
            conn.close()

    def stream(self, ref: str) -> Iterator[Record]:
        conn = _connect_ro(ref)
        try:
            for table in self._tables(conn):
                cur = conn.execute(f'SELECT * FROM "{table}"')
                for row in cur:
                    yield Record(entity=table, values=dict(row))
        finally:
            conn.close()


# Static structural check: SqliteConnector satisfies the Protocol.
_: SourceConnector = SqliteConnector()
