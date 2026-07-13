"""Pre-flight Advisor (P5) — inspect a source BEFORE import, advise settings.

Read-only, no hashing, no artifacts, no history. Surfaces risks the operator
should see before the raw data is ever read for transform, and recommends a PII
profile + a list of tables to exclude. Runs on the same connectors as the
pipeline; SQLite gets deep introspection (PK/FK/blobs/views/triggers/row counts).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .connectors.base import Structure
from .connectors.sqlite_conn import _PII_NAME, _connect_ro  # reuse heuristics/RO open

# Tables that should almost never be shipped to an external AI at all.
_SENSITIVE_TABLE = re.compile(
    r"(user|admin|auth|account|vault|secret|token|password|passwd|credential|"
    r"session|api_?key|login|permission|role)",
    re.IGNORECASE,
)
# Free-text column names that may hide PII regex can't catch inside prose.
_FREETEXT_NAME = re.compile(
    r"(note|comment|description|desc|remark|message|msg|body|content|bio|"
    r"about|address|detail|feedback|reason)",
    re.IGNORECASE,
)
_FREETEXT_TYPES = {"str"}
_LARGE_ROWS = 100_000


@dataclass
class Finding:
    severity: str          # info | warn | critical
    code: str              # sensitive-table | pii-freetext | no-pk | no-fk | blob | view | trigger | large-table
    target: str            # table or table.column
    message: str
    recommendation: str


@dataclass
class PreflightReport:
    site: str
    source_kind: str
    tables: int
    total_rows: int
    findings: list[Finding] = field(default_factory=list)
    recommended_pii_profile: str = "exclude"      # exclude | anonymize
    recommended_exclude_tables: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        order = {"critical": 0, "warn": 1, "info": 2}
        findings = sorted(self.findings, key=lambda f: order.get(f.severity, 9))
        return {
            "site": self.site,
            "source_kind": self.source_kind,
            "tables": self.tables,
            "total_rows": self.total_rows,
            "recommended_pii_profile": self.recommended_pii_profile,
            "recommended_exclude_tables": self.recommended_exclude_tables,
            "findings": [
                {"severity": f.severity, "code": f.code, "target": f.target,
                 "message": f.message, "recommendation": f.recommendation}
                for f in findings
            ],
        }


def _table_name(source_ref: str, fallback: str) -> str:
    return source_ref[len("table:"):] if source_ref.startswith("table:") else fallback


def inspect_sqlite(source_ref: str, structure: Structure) -> PreflightReport:
    report = PreflightReport(site=structure.site, source_kind="sqlite",
                             tables=len(structure.entities), total_rows=0)
    exclude: set[str] = set()
    freetext_pii = False

    conn = _connect_ro(source_ref)
    try:
        for ent in structure.entities:
            table = _table_name(ent.source_ref, ent.name)

            # sensitive table by name
            if _SENSITIVE_TABLE.search(table):
                exclude.add(table)
                report.findings.append(Finding(
                    "critical", "sensitive-table", table,
                    f"Table '{table}' looks like auth/secret data.",
                    "Exclude the whole table from the export.",
                ))

            # row count (large -> sample)
            try:
                n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except Exception:
                n = 0
            report.total_rows += n
            if n > _LARGE_ROWS:
                report.findings.append(Finding(
                    "warn", "large-table", table,
                    f"Table '{table}' has {n:,} rows.",
                    "Sample instead of reading every row.",
                ))

            # primary key present?
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            has_pk = any(c["pk"] for c in info)
            if not has_pk:
                report.findings.append(Finding(
                    "warn", "no-pk", table,
                    f"Table '{table}' has no primary key.",
                    "Relations may not round-trip; add a stable key or accept lower fidelity.",
                ))

            # blob columns
            for c in info:
                if (c["type"] or "").upper().startswith("BLOB"):
                    report.findings.append(Finding(
                        "warn", "blob", f"{table}.{c['name']}",
                        f"Column '{c['name']}' is BLOB.",
                        "Binary columns can't be represented as a command; will be skipped.",
                    ))

            # free-text PII risk
            for col in ent.columns:
                if (col.type in _FREETEXT_TYPES and _FREETEXT_NAME.search(col.name)
                        and not col.is_pii):
                    freetext_pii = True
                    report.findings.append(Finding(
                        "warn", "pii-freetext", f"{table}.{col.name}",
                        f"Free-text column '{col.name}' may contain PII the regex misses.",
                        "Use the ANONYMIZE profile, or exclude the column.",
                    ))

            # foreign keys on this table
            fks = conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
            if fks:
                report.__dict__.setdefault("_has_fk", True)

        # any FKs at all?
        if not report.__dict__.get("_has_fk"):
            report.findings.append(Finding(
                "info", "no-fk", structure.site,
                "No foreign keys found in the schema.",
                "Entity relations are implicit; the agent will infer them from names.",
            ))
        report.__dict__.pop("_has_fk", None)

        # views + triggers = behavioral logic not captured by table schema
        for kind in ("view", "trigger"):
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%'",
                (kind,),
            ).fetchall()
            for r in rows:
                report.findings.append(Finding(
                    "info", kind, r["name"],
                    f"{kind.capitalize()} '{r['name']}' holds logic not in the table schema.",
                    "Behavioral logic won't round-trip from schema alone; regenerate it manually.",
                ))
    finally:
        conn.close()

    report.recommended_exclude_tables = sorted(exclude)
    report.recommended_pii_profile = "anonymize" if freetext_pii else "exclude"
    return report


def inspect_sql(source_kind: str, source_ref: str, structure: Structure) -> PreflightReport:
    """SQLAlchemy-based advisor for Postgres/MySQL/MSSQL/Oracle (dialect-agnostic)."""
    from sqlalchemy import create_engine, inspect, text

    report = PreflightReport(site=structure.site, source_kind=source_kind,
                             tables=len(structure.entities), total_rows=0)
    exclude: set[str] = set()
    freetext_pii = False
    eng = create_engine(source_ref, pool_pre_ping=True)
    try:
        insp = inspect(eng)
        with eng.connect() as conn:
            has_fk = False
            for ent in structure.entities:
                table = _table_name(ent.source_ref, ent.name)
                if _SENSITIVE_TABLE.search(table):
                    exclude.add(table)
                    report.findings.append(Finding(
                        "critical", "sensitive-table", table,
                        f"Table '{table}' looks like auth/secret data.",
                        "Exclude the whole table from the export."))
                try:
                    n = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
                except Exception:
                    n = 0
                report.total_rows += n
                if n > _LARGE_ROWS:
                    report.findings.append(Finding(
                        "warn", "large-table", table, f"Table '{table}' has {n:,} rows.",
                        "Sample instead of reading every row."))
                pk = insp.get_pk_constraint(table).get("constrained_columns", [])
                if not pk:
                    report.findings.append(Finding(
                        "warn", "no-pk", table, f"Table '{table}' has no primary key.",
                        "Relations may not round-trip; add a stable key."))
                if insp.get_foreign_keys(table):
                    has_fk = True
                for col in ent.columns:
                    if col.type == "bytes":
                        report.findings.append(Finding(
                            "warn", "blob", f"{table}.{col.name}",
                            f"Column '{col.name}' is binary.",
                            "Binary columns can't be a command; will be skipped."))
                    if (col.type == "str" and _FREETEXT_NAME.search(col.name)
                            and not col.is_pii):
                        freetext_pii = True
                        report.findings.append(Finding(
                            "warn", "pii-freetext", f"{table}.{col.name}",
                            f"Free-text column '{col.name}' may contain PII.",
                            "Use the ANONYMIZE profile, or exclude the column."))
            if not has_fk:
                report.findings.append(Finding(
                    "info", "no-fk", structure.site, "No foreign keys found.",
                    "Entity relations are implicit; the agent infers them from names."))
            for kind in ("view",):
                try:
                    for v in insp.get_view_names():
                        report.findings.append(Finding(
                            "info", "view", v, f"View '{v}' holds logic not in tables.",
                            "Behavioral logic won't round-trip from schema alone."))
                except Exception:
                    pass
    finally:
        eng.dispose()
    report.recommended_exclude_tables = sorted(exclude)
    report.recommended_pii_profile = "anonymize" if freetext_pii else "exclude"
    return report


def inspect_structure(source_kind: str, structure: Structure,
                      pk_map: dict | None = None) -> PreflightReport:
    """Advisor from an already-parsed structure (no live connection) — used for
    .sql dumps. Row counts unknown (schema-only)."""
    pk_map = pk_map or {}
    report = PreflightReport(site=structure.site, source_kind=source_kind,
                             tables=len(structure.entities), total_rows=0)
    exclude: set[str] = set()
    freetext_pii = False
    for ent in structure.entities:
        table = _table_name(ent.source_ref, ent.name)
        if _SENSITIVE_TABLE.search(table):
            exclude.add(table)
            report.findings.append(Finding(
                "critical", "sensitive-table", table,
                f"Table '{table}' looks like auth/secret data.",
                "Exclude the whole table from the export."))
        if not pk_map.get(table):
            report.findings.append(Finding(
                "warn", "no-pk", table, f"Table '{table}' has no primary key.",
                "Relations may not round-trip; add a stable key."))
        for col in ent.columns:
            if col.type == "bytes":
                report.findings.append(Finding(
                    "warn", "blob", f"{table}.{col.name}",
                    f"Column '{col.name}' is binary.",
                    "Binary columns can't be a command; will be skipped."))
            if col.type == "str" and _FREETEXT_NAME.search(col.name) and not col.is_pii:
                freetext_pii = True
                report.findings.append(Finding(
                    "warn", "pii-freetext", f"{table}.{col.name}",
                    f"Free-text column '{col.name}' may contain PII.",
                    "Use the ANONYMIZE profile, or exclude the column."))
    report.recommended_exclude_tables = sorted(exclude)
    report.recommended_pii_profile = "anonymize" if freetext_pii else "exclude"
    return report


def run(source_kind: str, source_ref: str) -> PreflightReport:
    """Probe + introspect a source read-only and return advice. No persistence."""
    from .pipeline import get_connector, _SQL_KINDS  # lazy

    connector = get_connector(source_kind)
    connector.probe(source_ref)                 # validates the ref exists/reachable
    structure = connector.structure(source_ref)
    if source_kind == "sqlite":
        return inspect_sqlite(source_ref, structure)
    if source_kind in _SQL_KINDS:
        return inspect_sql(source_kind, source_ref, structure)
    if source_kind == "sqldump":
        return inspect_structure(source_kind, structure,
                                 pk_map=getattr(structure, "_pk_map", {}))
    # generic fallback for future connectors: structural findings only
    report = PreflightReport(site=structure.site, source_kind=source_kind,
                             tables=len(structure.entities), total_rows=0)
    for ent in structure.entities:
        table = _table_name(ent.source_ref, ent.name)
        if _SENSITIVE_TABLE.search(table):
            report.recommended_exclude_tables.append(table)
            report.findings.append(Finding(
                "critical", "sensitive-table", table,
                f"'{table}' looks like auth/secret data.",
                "Exclude it from the export.",
            ))
    return report
