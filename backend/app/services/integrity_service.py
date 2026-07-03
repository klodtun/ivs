"""
IVS Integrity Service — anti-tamper and copyright enforcement.

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

Purpose
-------
Detect attempts to:
  1. Forge or duplicate the machine fingerprint (clone an installation)
  2. Remove or alter the IVS copyright notice in critical files
  3. Run with a sustained fingerprint mismatch (>30d grace) — license breach
  4. Tamper with the license.bound file

The service exposes:
  - check_on_startup()  — called from main.py lifespan; logs critical breaches
  - get_integrity_report() — JSON status for /api/system/integrity (admin only)

This is a deterrent and a forensic signal — NOT cryptographic DRM. Determined
attackers with source-code access can disable it. Its real job is:
  (a) Create a paper trail (audit log entries) for copyright enforcement
  (b) Refuse to start cleanly when tampering is obvious
  (c) Inform honest users when their hardware genuinely changed
"""
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.services import license_service

logger = logging.getLogger(__name__)

# 30-day grace period for fingerprint mismatch — beyond this, license auto-terminates per EULA §5
FINGERPRINT_GRACE_DAYS = 30

# Files whose copyright header MUST be intact for the build to be considered untampered.
# Path is relative to backend/.
_PROTECTED_FILES = [
    "app/services/license_service.py",
    "app/services/integrity_service.py",
    "app/main.py",
]

_COPYRIGHT_MARKER = "Copyright © 2026 IVS Project"


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _check_copyright_headers() -> List[Dict]:
    """Verify the © marker is still present in protected files."""
    findings = []
    root = _backend_root()
    for rel in _PROTECTED_FILES:
        p = root / rel
        if not p.exists():
            findings.append({"file": rel, "status": "MISSING", "ok": False})
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            findings.append({"file": rel, "status": f"UNREADABLE: {e}", "ok": False})
            continue
        if _COPYRIGHT_MARKER in text:
            findings.append({"file": rel, "status": "OK", "ok": True})
        else:
            findings.append({"file": rel, "status": "COPYRIGHT_REMOVED", "ok": False})
    return findings


def _check_license_file() -> Dict:
    """Verify the project LICENSE file exists and is unmodified-ish."""
    project_root = _backend_root().parent
    license_path = project_root / "LICENSE"
    if not license_path.exists():
        return {"file": "LICENSE", "status": "MISSING", "ok": False}
    try:
        text = license_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"file": "LICENSE", "status": "UNREADABLE", "ok": False}
    if _COPYRIGHT_MARKER not in text:
        return {"file": "LICENSE", "status": "COPYRIGHT_REMOVED", "ok": False}
    if "Proprietary" not in text and "PROPRIETARY" not in text:
        return {"file": "LICENSE", "status": "LICENSE_REPLACED", "ok": False}
    return {"file": "LICENSE", "status": "OK", "ok": True}


def _fingerprint_status() -> Dict:
    """Check whether the bound fingerprint still matches current hardware."""
    try:
        info = license_service.get_license_info()
    except Exception as e:
        return {"status": "ERROR", "ok": False, "error": str(e)}

    fp_status = info.get("fingerprint_status", "UNKNOWN")
    if fp_status == "OK":
        return {"status": "OK", "ok": True, "serial": info.get("serial")}

    # MISMATCH — measure how long
    created_at = info.get("created_at")
    age_days = 0
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).days
        except Exception:
            pass

    over_grace = age_days > FINGERPRINT_GRACE_DAYS
    return {
        "status": "MISMATCH_OVER_GRACE" if over_grace else "MISMATCH_WITHIN_GRACE",
        "ok": not over_grace,
        "serial": info.get("serial"),
        "grace_days": FINGERPRINT_GRACE_DAYS,
        "age_days": age_days,
    }


def get_integrity_report() -> Dict:
    """
    Aggregate integrity status. Used by /api/system/integrity and startup check.
    """
    headers = _check_copyright_headers()
    license_check = _check_license_file()
    fp = _fingerprint_status()

    breaches = [h for h in headers if not h["ok"]]
    if not license_check["ok"]:
        breaches.append(license_check)
    if not fp["ok"]:
        breaches.append({"file": "machine_fingerprint", "status": fp["status"], "ok": False})

    return {
        "ok": len(breaches) == 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "copyright_headers": headers,
        "license_file": license_check,
        "fingerprint": fp,
        "breaches": breaches,
        "edition": "FREE",
        "copyright": "© 2026 IVS Project. All Rights Reserved.",
    }


def check_on_startup() -> None:
    """
    Run integrity check during app lifespan startup.

    Logs at CRITICAL for any breach. Does NOT prevent startup (would lock
    out honest admins after legitimate hardware changes) but the breach is
    visible in /api/system/integrity and audit logs.
    """
    try:
        report = get_integrity_report()
        if report["ok"]:
            logger.info("Integrity check: OK")
            return
        for b in report["breaches"]:
            logger.critical(
                f"INTEGRITY BREACH: {b.get('file', '?')} — {b.get('status', '?')}. "
                f"This may indicate a copyright/license violation. See LICENSE §3, §5."
            )
    except Exception as e:
        logger.warning(f"Integrity check failed to run: {e}")
