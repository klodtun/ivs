"""Round-trip acceptance test (P3) — the OpenCLI Bridge success metric.

Measures whether the emitted artifacts (cli-manifest.json) carry enough structure
to reconstruct the source system. Deterministic: reconstructs the schema FROM the
artifact, then diffs it against the live source structure, accounting for the PII
policy that was applied.

This is a STRUCTURAL fidelity check (tables + non-PII columns round-trip), the
automatable proxy for "an AI agent can regenerate the system". Behavioral identity
still needs the agent (stage 4 MCP) — this gates that the inputs are sufficient.

    fidelity = reconstructed_columns_correct / columns_expected_under_policy
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import OpenCliImport, OpenCliPiiProfile
from . import reader
from .pipeline import get_connector


@dataclass
class TableDiff:
    table: str
    expected: list[str]          # columns that SHOULD appear under the PII policy
    reconstructed: list[str]     # columns actually in the manifest
    dropped_pii: list[str]       # PII columns intentionally excluded
    missing: list[str] = field(default_factory=list)   # expected but absent (defect)
    extra: list[str] = field(default_factory=list)      # present but unexpected (leak/defect)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra


@dataclass
class RoundTripReport:
    import_id: int
    site: str
    pii_profile: str
    tables_total: int
    tables_matched: int
    columns_expected: int
    columns_correct: int
    pii_dropped: int
    diffs: list[TableDiff] = field(default_factory=list)

    @property
    def fidelity(self) -> float:
        if self.columns_expected == 0:
            return 1.0
        return self.columns_correct / self.columns_expected

    @property
    def passed(self) -> bool:
        # Lossless structural round-trip: every table present, no missing/extra cols.
        return (self.tables_matched == self.tables_total
                and self.fidelity == 1.0)

    def as_dict(self) -> dict:
        return {
            "import_id": self.import_id,
            "site": self.site,
            "pii_profile": self.pii_profile,
            "tables_total": self.tables_total,
            "tables_matched": self.tables_matched,
            "columns_expected": self.columns_expected,
            "columns_correct": self.columns_correct,
            "pii_dropped": self.pii_dropped,
            "fidelity": round(self.fidelity, 4),
            "passed": self.passed,
            "defects": [
                {"table": d.table, "missing": d.missing, "extra": d.extra}
                for d in self.diffs if not d.ok
            ],
        }


def run(db, imp: OpenCliImport) -> RoundTripReport:
    """Diff artifact-reconstructed schema against the live source."""
    profile = imp.pii_profile

    # Ground truth: re-introspect the source (read-only).
    connector = get_connector(imp.source_kind)
    structure = connector.structure(imp.source_ref)

    # Artifact: what an agent would consume.
    manifest = reader.read_manifest(imp) or []
    # map "table:<name>" -> manifest columns
    manifest_by_table: dict[str, list[str]] = {}
    for cmd in manifest:
        src = cmd.get("sourceFile", "")
        if src.startswith("table:"):
            manifest_by_table[src[len("table:"):]] = list(cmd.get("columns", []))

    diffs: list[TableDiff] = []
    tables_matched = 0
    cols_expected = 0
    cols_correct = 0
    pii_dropped = 0

    for ent in structure.entities:
        table = ent.source_ref[len("table:"):] if ent.source_ref.startswith("table:") else ent.name
        if profile == OpenCliPiiProfile.EXCLUDE:
            expected = [c.name for c in ent.columns if not c.is_pii]
            dropped = [c.name for c in ent.columns if c.is_pii]
        else:  # ANONYMIZE keeps all columns (values redacted at read time)
            expected = [c.name for c in ent.columns]
            dropped = []
        pii_dropped += len(dropped)

        recon = manifest_by_table.get(table, [])
        missing = [c for c in expected if c not in recon]
        extra = [c for c in recon if c not in expected]

        diff = TableDiff(table=table, expected=expected, reconstructed=recon,
                         dropped_pii=dropped, missing=missing, extra=extra)
        diffs.append(diff)

        cols_expected += len(expected)
        cols_correct += len([c for c in expected if c in recon])
        if diff.ok and table in manifest_by_table:
            tables_matched += 1

    return RoundTripReport(
        import_id=imp.id,
        site=structure.site,
        pii_profile=profile.value,
        tables_total=len(structure.entities),
        tables_matched=tables_matched,
        columns_expected=cols_expected,
        columns_correct=cols_correct,
        pii_dropped=pii_dropped,
        diffs=diffs,
    )
