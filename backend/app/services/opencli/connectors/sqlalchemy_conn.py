"""SQL connector (P10) — one connector for Postgres / MySQL / SQL Server / Oracle.

Uses SQLAlchemy reflection, so a single dialect-agnostic implementation covers
every supported RDBMS. `source_ref` is a SQLAlchemy URL, e.g.:
  postgresql+psycopg2://user:pass@host:5432/db
  mysql+pymysql://user:pass@host/db
  mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server
  oracle+oracledb://user:pass@host:1521/?service_name=ORCL

The DB driver is imported lazily by SQLAlchemy on connect — install the matching
driver (psycopg2 / pymysql / pyodbc / oracledb) for the target. Reads are
introspection + SELECT only; nothing is written to the source.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterator

from .base import Column, Entity, Record, SourceConnector, SourceMeta, Structure
from .sqlite_conn import _PII_NAME   # reuse the PII column-name heuristic

# SQLAlchemy generic type -> our type tag
_TYPE_TAGS = ("int", "float", "bool", "bytes", "str")


def _map_type(sa_type) -> str:
    t = str(sa_type).upper()
    if any(k in t for k in ("INT", "SERIAL", "NUMBER")):
        return "int"
    if any(k in t for k in ("FLOAT", "REAL", "DOUBLE", "DECIMAL", "NUMERIC")):
        return "float"
    if "BOOL" in t:
        return "bool"
    if any(k in t for k in ("BLOB", "BYTEA", "BINARY", "RAW")):
        return "bytes"
    return "str"


def _slug_from_url(url: str) -> str:
    # last path segment (db name) or host
    tail = re.split(r"[/@?]", url.rstrip("/"))
    name = next((p for p in reversed(tail) if p), "sql")
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "sql"


class SqlAlchemyConnector:
    strategy = "local"

    def _engine(self, ref: str):
        from sqlalchemy import create_engine  # lazy
        # future=True keeps 2.0 semantics; pool_pre_ping avoids stale conns
        return create_engine(ref, pool_pre_ping=True)

    def probe(self, ref: str) -> SourceMeta:
        from sqlalchemy import inspect
        # a file path is not a live-DB URL — the most common wrong pick
        if ref.startswith("file://") or ref.endswith(".sql") or "://" not in ref:
            raise ValueError(
                "This looks like a file, not a live-database URL. For a .sql export "
                "choose source kind 'SQL dump (.sql)'; for a live DB use a URL like "
                "postgresql://user:pass@host/db")
        eng = self._engine(ref)
        try:
            n = len(inspect(eng).get_table_names())
        finally:
            eng.dispose()
        return SourceMeta(kind="sql", ref=ref, size_bytes=n)  # #tables as a cheap size

    def structure(self, ref: str) -> Structure:
        from sqlalchemy import inspect
        eng = self._engine(ref)
        try:
            insp = inspect(eng)
            entities: list[Entity] = []
            for table in sorted(insp.get_table_names()):
                cols = []
                for c in insp.get_columns(table):
                    cols.append(Column(
                        name=c["name"],
                        type=_map_type(c["type"]),
                        is_pii=bool(_PII_NAME.search(c["name"])),
                    ))
                entities.append(Entity(
                    name=f"list-{table}", columns=cols,
                    access="read", source_ref=f"table:{table}",
                ))
            return Structure(site=_slug_from_url(ref), entities=entities)
        finally:
            eng.dispose()

    def stream(self, ref: str, limit: int = 1000) -> Iterator[Record]:
        from sqlalchemy import inspect, text
        eng = self._engine(ref)
        try:
            insp = inspect(eng)
            with eng.connect() as conn:
                for table in insp.get_table_names():
                    rows = conn.execute(text(f'SELECT * FROM "{table}"').execution_options(
                        stream_results=True))
                    for i, row in enumerate(rows):
                        if i >= limit:
                            break
                        yield Record(entity=table, values=dict(row._mapping))
        finally:
            eng.dispose()

    def fingerprint(self, ref: str) -> tuple[str, int]:
        """Stage-1 hash for a live DB: deterministic schema fingerprint (tables,
        columns, types, PK/FK) + total row count. No file to hash, so this proves
        the analyzed schema matches the source without copying data."""
        from sqlalchemy import inspect, text
        eng = self._engine(ref)
        try:
            insp = inspect(eng)
            schema = {}
            total_rows = 0
            with eng.connect() as conn:
                for table in sorted(insp.get_table_names()):
                    cols = [(c["name"], str(c["type"])) for c in insp.get_columns(table)]
                    pk = insp.get_pk_constraint(table).get("constrained_columns", [])
                    fks = [(fk.get("referred_table"), tuple(fk.get("constrained_columns", [])))
                           for fk in insp.get_foreign_keys(table)]
                    schema[table] = {"cols": cols, "pk": pk, "fk": fks}
                    try:
                        total_rows += conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
                    except Exception:
                        pass
            blob = json.dumps(schema, sort_keys=True).encode()
            return hashlib.sha256(blob).hexdigest(), total_rows
        finally:
            eng.dispose()


_: SourceConnector = SqlAlchemyConnector()
