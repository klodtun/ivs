"""SQL dump-file connector (P12) — read a `.sql` export without a live DB.

Parses `CREATE TABLE` DDL from a mysqldump / pg_dump / generic `.sql` file to get
the schema. It deliberately IGNORES `INSERT` rows — the bridge only needs
structure, so no real data (or PII) is ever read. The whole file is SHA-256'd,
so the importer can `sha256sum` it and verify (Row1). No temp DB, no engine, no
data load — faster and more compliant than restore-then-drop.
"""
from __future__ import annotations

import hashlib
import os
import re

from .base import Column, Entity, Record, SourceConnector, SourceMeta, Structure
from .sqlite_conn import _PII_NAME

# CREATE TABLE `name` (  ... )  — backtick / double-quote / bare identifier
_CREATE = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(?P<name>\w+)[`"\]]?\s*\((?P<body>.*?)\)\s*(?:ENGINE|;|/\*)',
    re.IGNORECASE | re.DOTALL,
)
# a column line: `col` type ...   (skip constraint lines)
_COL = re.compile(r'^\s*[`"\[]?(?P<col>\w+)[`"\]]?\s+(?P<type>[A-Za-z]+)', re.IGNORECASE)
_SKIP = re.compile(r'^\s*(PRIMARY|UNIQUE|KEY|INDEX|CONSTRAINT|FOREIGN|FULLTEXT|SPATIAL|CHECK)\b',
                   re.IGNORECASE)
# PRIMARY KEY, inline or via ALTER TABLE ... ADD PRIMARY KEY
_ALTER_PK = re.compile(
    r'ALTER\s+TABLE\s+[`"\[]?(\w+)[`"\]]?.*?PRIMARY\s+KEY\s*\(\s*[`"\[]?(\w+)',
    re.IGNORECASE | re.DOTALL,
)

_TYPE = {
    "int": "int", "integer": "int", "tinyint": "int", "smallint": "int",
    "mediumint": "int", "bigint": "int", "serial": "int", "bit": "int",
    "decimal": "float", "numeric": "float", "float": "float", "double": "float",
    "real": "float", "bool": "bool", "boolean": "bool",
    "blob": "bytes", "tinyblob": "bytes", "mediumblob": "bytes", "longblob": "bytes",
    "binary": "bytes", "varbinary": "bytes", "bytea": "bytes",
}


def _map_type(t: str) -> str:
    return _TYPE.get(t.lower(), "str")


def _path(ref: str) -> str:
    return ref[len("file://"):] if ref.startswith("file://") else ref


def _read(ref: str) -> str:
    with open(_path(ref), "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


class SqlDumpConnector:
    strategy = "local"

    def probe(self, ref: str) -> SourceMeta:
        p = _path(ref)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"sql dump not found: {ref}")
        return SourceMeta(kind="sqldump", ref=ref, size_bytes=os.path.getsize(p))

    def _pk_map(self, sql: str) -> dict[str, set[str]]:
        pk: dict[str, set[str]] = {}
        for tbl, col in _ALTER_PK.findall(sql):
            pk.setdefault(tbl, set()).add(col)
        return pk

    def structure(self, ref: str) -> Structure:
        sql = _read(ref)
        pk_map = self._pk_map(sql)
        entities: list[Entity] = []
        for m in _CREATE.finditer(sql):
            table = m.group("name")
            cols: list[Column] = []
            for line in m.group("body").splitlines():
                if _SKIP.match(line):
                    continue
                cm = _COL.match(line)
                if not cm:
                    continue
                # inline PRIMARY KEY on the column
                if re.search(r'PRIMARY\s+KEY', line, re.IGNORECASE):
                    pk_map.setdefault(table, set()).add(cm.group("col"))
                cols.append(Column(
                    name=cm.group("col"),
                    type=_map_type(cm.group("type")),
                    is_pii=bool(_PII_NAME.search(cm.group("col"))),
                ))
            entities.append(Entity(
                name=f"list-{table}", columns=cols, access="read",
                source_ref=f"table:{table}",
            ))
        slug = re.sub(r"[^a-z0-9]+", "-",
                      os.path.splitext(os.path.basename(_path(ref)))[0].lower()).strip("-") or "dump"
        st = Structure(site=slug, entities=entities)
        st._pk_map = pk_map          # attached for the preflight advisor
        return st

    def stream(self, ref: str) -> "list[Record]":
        # Intentionally empty: the bridge needs schema only; INSERT rows are never
        # parsed, so no real data or PII is read from the dump.
        raise NotImplementedError("sqldump is schema-only (INSERT rows are not read)")

    def file_sha256(self, ref: str) -> tuple[str, int]:
        h = hashlib.sha256()
        size = 0
        with open(_path(ref), "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
                size += len(chunk)
        return h.hexdigest(), size


_: SourceConnector = SqlDumpConnector()
