#!/usr/bin/env python3
"""Dogfood the OpenCLI Bridge (P1): import IVS's own ivs.db and emit artifacts.

    cd backend && python ../scripts/dogfood_bridge.py

Reads backend/data/ivs.db read-only, hashes it, writes cli-manifest.json +
structure.md under deployed_apps/_bridge/<id>/, prints a receipt. No UI, no MCP.
"""
import os
import sys

# run from repo root or backend/ — make `app` importable either way
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BACKEND = os.path.join(REPO, "backend")
sys.path.insert(0, BACKEND)

from app.database import SessionLocal, Base, engine  # noqa: E402
from app.models import OpenCliPiiProfile  # noqa: E402
from app.services.opencli import pipeline  # noqa: E402

DB_PATH = os.path.join(BACKEND, "data", "ivs.db")


def main() -> int:
    Base.metadata.create_all(bind=engine)  # ensure new tables exist
    if not os.path.isfile(DB_PATH):
        print(f"!! ivs.db not found at {DB_PATH}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        imp = pipeline.run_import(
            db,
            importer_id=None,          # CLI dogfood — no user
            source_kind="sqlite",
            source_ref=DB_PATH,
            pii_profile=OpenCliPiiProfile.EXCLUDE,
            request=None,              # no audit row in CLI context
            user=None,
        )
    finally:
        db.close()

    print("=== OpenCLI Bridge dogfood receipt ===")
    print(f"import id     : {imp.id}")
    print(f"status        : {imp.status.value}")
    print(f"source        : {imp.source_kind}:{imp.source_ref}")
    print(f"source bytes  : {imp.source_bytes:,}")
    print(f"sha256(raw)   : {imp.sha256_raw}")
    print(f"pii profile   : {imp.pii_profile.value}")
    print(f"commands      : {imp.command_count}")
    print(f"manifest sha  : {imp.manifest_sha}")
    print(f"artifact dir  : {imp.artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
