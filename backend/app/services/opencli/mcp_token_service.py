"""MCP token service (P9, Enterprise) — connect external AI agents.

An external agent authenticates to the project's MCP surface with a scoped
token. Only the SHA-256 hash is stored; the plaintext is shown once at creation.
Tokens are per-project so an agent sees only what it's granted.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.models import OpenCliMcpToken, utcnow

_PREFIX = "ocli_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(db: Session, *, project_id: int, name: str, scope: str,
           created_by: Optional[int]) -> tuple[str, OpenCliMcpToken]:
    """Mint a token. Returns (plaintext, row). Plaintext is never stored/returned again."""
    token = _PREFIX + secrets.token_urlsafe(32)
    row = OpenCliMcpToken(
        project_id=project_id,
        name=name.strip() or "agent",
        token_hash=_hash(token),
        prefix=token[:12],
        scope=scope if scope in ("read", "read_write") else "read",
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return token, row


def list_tokens(db: Session, project_id: int) -> list[dict]:
    rows = (db.query(OpenCliMcpToken)
            .filter(OpenCliMcpToken.project_id == project_id)
            .order_by(OpenCliMcpToken.created_at.desc()).all())
    return [{
        "id": r.id, "name": r.name, "prefix": r.prefix, "scope": r.scope,
        "created_at": r.created_at.isoformat(),
        "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        "revoked": r.revoked_at is not None,
    } for r in rows]


def revoke(db: Session, token_id: int) -> Optional[OpenCliMcpToken]:
    row = db.get(OpenCliMcpToken, token_id)
    if row is None:
        return None
    row.revoked_at = utcnow()
    db.add(row)
    db.commit()
    return row


def verify(db: Session, token: str) -> Optional[OpenCliMcpToken]:
    """Resolve a presented token to its row (valid + not revoked). For a future
    HTTP-MCP gateway to authenticate external agents. Updates last_used_at."""
    row = (db.query(OpenCliMcpToken)
           .filter(OpenCliMcpToken.token_hash == _hash(token),
                   OpenCliMcpToken.revoked_at.is_(None)).first())
    if row:
        row.last_used_at = utcnow()
        db.add(row)
        db.commit()
    return row
