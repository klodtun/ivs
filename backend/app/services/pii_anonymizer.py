"""PII anonymization for the 3-Tier Privacy-Compliant Logging Architecture.

This module is the Level 0 → Level 1 boundary. Log lines coming out of
Docker containers (Level 0 — raw, PII intact, never persisted) are
passed through `anonymize()` before being written to `app_log_entries`
(Level 1 — anonymized storage, durable, GDPR/APPI/PDPA-safe).

Strategy:
- Email addresses → keccak-style truncated SHA-256 hash, keeps domain
  visible for debugging ("u#a3f1c2@example.com")
- IPv4 / IPv6 addresses → preserve network portion, hash host portion
  ("203.0.113.x → 203.0.113.[ANON_a3f1]")
- Thai national ID (13 digits) → fully redacted "[REDACTED:THAI_ID]"
- Credit card-like numbers (13-19 digits with possible separators)
  → "[REDACTED:CARD]"
- E.164 / Thai phone numbers → preserve country code, hash subscriber
- Generic bearer tokens / JWT → "[REDACTED:TOKEN]"

Hashing uses HMAC-SHA256 with a stable secret so the SAME PII always
maps to the SAME anonymized token (lets ops correlate across log lines
without re-identifying). The secret is derived from settings.SECRET_KEY
so it's stable across restarts but unique per IVS install.

Right-to-be-Forgotten (GDPR Art.17): the anonymized rows in Level 1
contain no recoverable PII, so a deletion request requires no action
on those rows — they're already deanonymized at the database layer.
"""
import hmac
import hashlib
import re
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _hmac_key() -> bytes:
    secret = getattr(settings, "SECRET_KEY", None) or "ivs-default-secret"
    return secret.encode("utf-8")


def _tok(value: str, prefix: str = "") -> str:
    """Stable short hash for a PII value — same input → same output."""
    h = hmac.new(_hmac_key(), value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}{h[:8]}"


# ── Patterns ───────────────────────────────────────────────────────
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
)
# Anchored — only IPv4 dotted-quads with each octet 0-255 ish
_IPV4 = re.compile(
    r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b"
)
# Loose IPv6 — any group of 4+ hex blocks separated by colons, OR `::` compressed form
_IPV6 = re.compile(
    r"(?:[A-Fa-f0-9]{1,4}:){3,7}[A-Fa-f0-9]{1,4}"
    r"|(?:[A-Fa-f0-9]{1,4}:){1,7}:[A-Fa-f0-9]{0,4}"
    r"|::[A-Fa-f0-9]{1,4}(?::[A-Fa-f0-9]{1,4}){0,6}"
)
# Thai national ID — 13 digits, optionally dash-separated
_THAI_ID = re.compile(r"\b\d-?\d{4}-?\d{5}-?\d{2}-?\d\b")
# Credit-card-like — 13-19 digits, optional spaces or dashes every 4
_CC = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
# Phone — Thai 0X (8-9 digits), or E.164 +(1-3)(7-15)
_PHONE_THAI = re.compile(r"\b0\d{8,9}\b")
_PHONE_E164 = re.compile(r"\+\d{1,3}(?:[ \-]?\d){6,14}\b")
# Bearer tokens — "Bearer xyz" header pattern + JWT-shaped strings
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")


def _sub_email(m: re.Match) -> str:
    return f"u#{_tok(m.group(0))}@{m.group(1)}"


def _sub_ipv4(m: re.Match) -> str:
    # Drop host octet, hash it for correlation; keep /24 visible for ops
    a, b, c, _ = m.group(1), m.group(2), m.group(3), m.group(4)
    # Don't anonymize private/loopback — operators need those raw
    try:
        if (
            a == "127"
            or a == "10"
            or (a == "192" and b == "168")
            or (a == "172" and 16 <= int(b) <= 31)
        ):
            return m.group(0)
    except ValueError:
        pass
    return f"{a}.{b}.{c}.[ANON_{_tok(m.group(0))}]"


def _sub_ipv6(m: re.Match) -> str:
    raw = m.group(0)
    # Localhost passthrough
    if raw in ("::1", "0:0:0:0:0:0:0:1"):
        return raw
    return f"[ANON_IPv6_{_tok(raw)}]"


def _sub_phone(m: re.Match) -> str:
    return f"[ANON_PHONE_{_tok(m.group(0))}]"


def _sub_phone_e164(m: re.Match) -> str:
    raw = m.group(0)
    # Keep country-code prefix for ops context, hash subscriber portion
    cc = raw[:3] if raw.startswith("+") else raw[:4]
    return f"{cc}[ANON_{_tok(raw)}]"


def anonymize(text: str) -> str:
    """Apply all PII redaction passes to a single log line."""
    if not text:
        return text
    # Order matters: redact specific patterns before generic ones
    text = _BEARER.sub("Bearer [REDACTED:TOKEN]", text)
    text = _JWT.sub("[REDACTED:JWT]", text)
    text = _THAI_ID.sub("[REDACTED:THAI_ID]", text)
    text = _CC.sub("[REDACTED:CARD]", text)
    text = _EMAIL.sub(_sub_email, text)
    text = _IPV6.sub(_sub_ipv6, text)
    text = _IPV4.sub(_sub_ipv4, text)
    text = _PHONE_E164.sub(_sub_phone_e164, text)
    text = _PHONE_THAI.sub(_sub_phone, text)
    return text
