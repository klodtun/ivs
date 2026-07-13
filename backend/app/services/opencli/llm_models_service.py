"""Multi-model registry (P15) — several AI agents help build code.

Register multiple AI models (each = provider + model + base_url + a key from the
IVS Vault/คลัง API Key). Different models can build different modules (multi-agent).
Keys are never stored here — resolved from the Vault at call time.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import OpenCliLlmModel, VaultKey
from app.services.vault_service import vault_service

from .llm.base import ProviderConfig
from . import regen_service


def create(db: Session, *, label: str, provider: str, model: str,
           base_url: Optional[str], vault_key_id: Optional[int],
           created_by: Optional[int]) -> OpenCliLlmModel:
    row = OpenCliLlmModel(
        label=label.strip() or model, provider=provider, model=model,
        base_url=(base_url or None), vault_key_id=vault_key_id, created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _key_name(db: Session, vault_key_id: Optional[int]) -> Optional[str]:
    if not vault_key_id:
        return None
    vk = db.get(VaultKey, vault_key_id)
    return vk.name if vk else None


def list_models(db: Session) -> list[dict]:
    rows = db.query(OpenCliLlmModel).order_by(OpenCliLlmModel.created_at.desc()).all()
    return [{
        "id": r.id, "label": r.label, "provider": r.provider, "model": r.model,
        "base_url": r.base_url or "", "vault_key_id": r.vault_key_id,
        "vault_key_name": _key_name(db, r.vault_key_id),
    } for r in rows]


def delete(db: Session, model_id: int) -> bool:
    row = db.get(OpenCliLlmModel, model_id)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def resolve(db: Session, model_id: int) -> ProviderConfig:
    """Build a ProviderConfig for a registered model — key decrypted from Vault."""
    row = db.get(OpenCliLlmModel, model_id)
    if not row:
        raise ValueError(f"AI model #{model_id} not found")
    key = None
    if row.vault_key_id:
        vk = db.get(VaultKey, row.vault_key_id)
        if vk:
            key = vault_service.decrypt(vk.encrypted_value)
    return ProviderConfig(provider=row.provider, model=row.model,
                          base_url=row.base_url or None, api_key=key)


def test(db: Session, model_id: int) -> dict:
    """Probe one registered model → {ok, detail} for a ready/not-ready badge."""
    cfg = resolve(db, model_id)
    return regen_service.test_cfg(cfg)
