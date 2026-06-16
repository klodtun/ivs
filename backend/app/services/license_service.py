"""
IVS Machine Fingerprint + Serial Number Service.

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

Tampering with, removing, or circumventing this module constitutes a material
breach of the EULA (§3.5, §5). The machine fingerprint and serial number
algorithms are trade secrets of the IVS Project.

Serial format: IVS-{EDITION}-{REGION}-{NONCE}-{CHECKSUM}  (23 chars total)
  IVS        = product prefix (3)
  EDITION    = FREE | LITE | STD | PRO | ENT  (3-4 chars, padded by design)
  REGION     = TH | EU | JP | GL  (2 chars)
  NONCE      = 8 Crockford-base32 chars, random at first boot
  CHECKSUM   = HMAC-SHA256("IVS-ED-RG-NONCE", SECRET_KEY)[:4] uppercase hex

Fingerprint: HMAC-SHA256(MAC + cpu_vendor + mobo_serial, SECRET_KEY)[:16]
Stored at:   ~/.ivs/license.bound  (JSON)
"""

import hashlib
import hmac
import json
import os
import platform
import random
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

# --------------------------------------------------------------------------- #
# Nonce alphabet — excludes 0/O/1/I/L to avoid hand-copy errors
# 30 chars: digits 2-9 + uppercase A-Z minus I, L, O
# --------------------------------------------------------------------------- #
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"  # 30 chars, unambiguous

BOUND_FILE = Path.home() / ".ivs" / "license.bound"

EDITIONS = {"FREE", "LITE", "STD", "PRO", "ENT"}
REGIONS = {"TH", "EU", "JP", "GL"}


# --------------------------------------------------------------------------- #
# Fingerprint collection
# --------------------------------------------------------------------------- #

def _get_mac() -> str:
    """Primary MAC of the default interface as 12 hex chars (no colons)."""
    try:
        mac = uuid.getnode()
        # uuid.getnode() falls back to random if no real MAC — detect that
        if mac >> 40 & 1:  # multicast bit set = random fallback
            return "NOMAC"
        return format(mac, "012x").upper()
    except Exception:
        return "NOMAC"


def _get_cpu_vendor() -> str:
    """CPU brand string, lowercased, first 32 chars."""
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL, timeout=3,
            ).decode().strip()
            return out[:32].lower()
        # Linux
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()[:32].lower()
    except Exception:
        pass
    return platform.processor()[:32].lower() or "unknown"


def _get_mobo_serial() -> str:
    """Motherboard serial (Linux dmidecode / macOS serial)."""
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(
                ["system_profiler", "SPHardwareDataType"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode()
            for line in out.splitlines():
                if "Serial Number" in line:
                    return line.split(":", 1)[1].strip()
        else:
            out = subprocess.check_output(
                ["dmidecode", "-s", "baseboard-serial-number"],
                stderr=subprocess.DEVNULL, timeout=3,
            ).decode().strip()
            if out and out not in ("None", "To be filled by O.E.M.", ""):
                return out
    except Exception:
        pass
    return "NOSERIAL"


def compute_fingerprint() -> str:
    """SHA256(MAC + cpu_vendor + mobo_serial, key=SECRET_KEY)[:16] hex."""
    raw = _get_mac() + "|" + _get_cpu_vendor() + "|" + _get_mobo_serial()
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16].upper()


# --------------------------------------------------------------------------- #
# Nonce + checksum
# --------------------------------------------------------------------------- #

def _random_nonce(length: int = 8) -> str:
    return "".join(random.choices(_ALPHABET, k=length))


def _checksum(serial_prefix: str) -> str:
    """HMAC-SHA256(serial_prefix, SECRET_KEY)[:4] uppercase hex."""
    h = hmac.new(
        settings.SECRET_KEY.encode(),
        serial_prefix.encode(),
        hashlib.sha256,
    ).hexdigest()
    return h[:4].upper()


# --------------------------------------------------------------------------- #
# Serial number assembly / validation
# --------------------------------------------------------------------------- #

def build_serial(edition: str, region: str, nonce: str) -> str:
    prefix = f"IVS-{edition}-{region}-{nonce}"
    ck = _checksum(prefix)
    return f"{prefix}-{ck}"


def verify_serial(serial: str) -> bool:
    parts = serial.split("-")
    if len(parts) != 5 or parts[0] != "IVS":
        return False
    prefix = "-".join(parts[:4])
    return hmac.compare_digest(_checksum(prefix), parts[4].upper())


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def _load_bound() -> Optional[dict]:
    if not BOUND_FILE.exists():
        return None
    try:
        return json.loads(BOUND_FILE.read_text())
    except Exception:
        return None


def _save_bound(data: dict) -> None:
    BOUND_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOUND_FILE.write_text(json.dumps(data, indent=2))


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

# Editions that include multi-service support (apps needing a separate
# database container: Postgres/MySQL/Redis/Mongo). Free/Lite/Std are
# single-container only.
EDITIONS_WITH_EXTERNAL_DB = {"PRO", "ENT"}


def current_edition() -> str:
    """Resolve the running edition. Reads the bound license, falling back
    to the IVS_EDITION env var, then FREE. Single source of truth for any
    feature gate."""
    bound = _load_bound()
    if bound and bound.get("edition") in EDITIONS:
        return bound["edition"]
    env = os.getenv("IVS_EDITION", "FREE").upper()
    return env if env in EDITIONS else "FREE"


def edition_supports_external_db(edition: Optional[str] = None) -> bool:
    """True if the edition may deploy apps that need a separate DB container."""
    ed = (edition or current_edition()).upper()
    return ed in EDITIONS_WITH_EXTERNAL_DB


def get_license_info(edition: str = "FREE", region: str = "TH") -> dict:
    """
    Return (and lazily create) the machine's license info.

    On first call: generate nonce + serial, bind to machine fingerprint.
    On subsequent calls: load from ~/.ivs/license.bound and verify fingerprint
    still matches — if the hardware changed flag it as 'MISMATCH'.
    """
    edition = edition.upper() if edition.upper() in EDITIONS else "FREE"
    region = region.upper() if region.upper() in REGIONS else "TH"

    bound = _load_bound()
    current_fp = compute_fingerprint()

    if bound is None:
        # First boot — generate and persist
        nonce = _random_nonce()
        serial = build_serial(edition, region, nonce)
        bound = {
            "serial": serial,
            "edition": edition,
            "region": region,
            "nonce": nonce,
            "fingerprint": current_fp,
            "created_at": _utcnow_iso(),
        }
        _save_bound(bound)

    fp_status = "OK" if bound.get("fingerprint") == current_fp else "MISMATCH"

    return {
        "serial": bound["serial"],
        "edition": bound.get("edition", "FREE"),
        "region": bound.get("region", "TH"),
        "fingerprint": bound["fingerprint"],
        "fingerprint_current": current_fp,
        "fingerprint_status": fp_status,
        "created_at": bound.get("created_at"),
        "bound_file": str(BOUND_FILE),
        "serial_valid": verify_serial(bound["serial"]),
    }


def _utcnow_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
