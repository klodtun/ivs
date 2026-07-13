#!/usr/bin/env python3
"""Round-trip acceptance test (P3) — the OpenCLI Bridge success metric.

    cd backend && python ../scripts/roundtrip_bridge.py [import_id]

If no import_id: create a fresh import of ivs.db, then verify it.
Reconstructs the schema from the emitted artifacts and diffs it against the
live source. Exits non-zero if structural fidelity < 1.0 (a defect).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), "backend")
sys.path.insert(0, BACKEND)

from app.database import SessionLocal, Base, engine  # noqa: E402
from app.models import OpenCliImport, OpenCliPiiProfile  # noqa: E402
from app.services.opencli import pipeline, roundtrip  # noqa: E402

DB_PATH = os.path.join(BACKEND, "data", "ivs.db")


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if len(sys.argv) > 1:
            imp = db.get(OpenCliImport, int(sys.argv[1]))
            if imp is None:
                print(f"!! import #{sys.argv[1]} not found", file=sys.stderr)
                return 2
        else:
            imp = pipeline.run_import(
                db, importer_id=None, source_kind="sqlite",
                source_ref=DB_PATH, pii_profile=OpenCliPiiProfile.EXCLUDE,
            )
            print(f"[*] created import #{imp.id} for round-trip")

        report = roundtrip.run(db, imp)
    finally:
        db.close()

    d = report.as_dict()
    print("=== OpenCLI Bridge round-trip report ===")
    print(json.dumps(d, indent=2, ensure_ascii=False))
    print()
    print(f"fidelity: {report.fidelity:.1%}  "
          f"tables {report.tables_matched}/{report.tables_total}  "
          f"cols {report.columns_correct}/{report.columns_expected}  "
          f"pii-dropped {report.pii_dropped}")
    print("RESULT:", "PASS ✅" if report.passed else "FAIL ❌")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
