"""Embedded regeneration service (P6) — brief → configured LLM → candidate app.

Provider-neutral: reads which provider to use from system_config, decrypts the
API key with the existing vault encryption, calls the provider, writes any
generated files to a candidate dir, and runs the deploy-time structural check.
Default provider is `manual` (no external call), so this works with no key.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import OpenCliImport, SystemConfig
from app.services.vault_service import vault_service

from . import reader, regen
from .llm import registry
from .llm.base import ProviderConfig

# system_config keys
_K_PROVIDER = "opencli.llm.provider"
_K_MODEL = "opencli.llm.model"
_K_BASE_URL = "opencli.llm.base_url"
_K_API_KEY = "opencli.llm.api_key_enc"   # stored encrypted via vault_service


def _get(db: Session, key: str) -> Optional[str]:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return row.value if row and row.value else None


def _upsert(db: Session, key: str, value: str) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemConfig(key=key, value=value))


def get_config(db: Session) -> dict:
    """Public config — never returns the key itself, only whether one is set."""
    return {
        "provider": _get(db, _K_PROVIDER) or registry.DEFAULT_PROVIDER,
        "model": _get(db, _K_MODEL) or "",
        "base_url": _get(db, _K_BASE_URL) or "",
        "has_key": bool(_get(db, _K_API_KEY)),
        "available_providers": registry.available(),
    }


def set_config(db: Session, *, provider: str, model: Optional[str] = None,
               base_url: Optional[str] = None, api_key: Optional[str] = None) -> dict:
    registry.get(provider)  # validate
    _upsert(db, _K_PROVIDER, provider)
    if model is not None:
        _upsert(db, _K_MODEL, model)
    if base_url is not None:
        _upsert(db, _K_BASE_URL, base_url)
    if api_key:  # only overwrite when a new key is supplied; encrypt at rest
        _upsert(db, _K_API_KEY, vault_service.encrypt(api_key))
    db.commit()
    return get_config(db)


def _resolve(db: Session) -> ProviderConfig:
    enc = _get(db, _K_API_KEY)
    return ProviderConfig(
        provider=_get(db, _K_PROVIDER) or registry.DEFAULT_PROVIDER,
        model=_get(db, _K_MODEL) or None,
        base_url=_get(db, _K_BASE_URL) or None,
        api_key=vault_service.decrypt(enc) if enc else None,
    )


def test_config(db: Session) -> dict:
    return test_cfg(_resolve(db))


def test_cfg(cfg) -> dict:
    """Probe a provider config → {ok, detail}. Reused by the multi-model registry."""
    provider = cfg.provider
    if provider == "manual":
        return {"provider": provider, "ok": True,
                "detail": "Manual mode — no provider needed."}

    if provider == "anthropic":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return {"provider": provider, "ok": False,
                    "detail": "anthropic SDK not installed (pip install anthropic)."}
        if not cfg.api_key:
            return {"provider": provider, "ok": False, "detail": "No API key set."}
        try:
            client = anthropic.Anthropic(api_key=cfg.api_key, base_url=cfg.base_url or None)
            client.models.list()
            return {"provider": provider, "ok": True,
                    "detail": f"Ready ({cfg.model or 'claude-opus-4-8'})."}
        except Exception as e:  # network/auth
            return {"provider": provider, "ok": False, "detail": str(e)[:200]}

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            return {"provider": provider, "ok": False,
                    "detail": "openai SDK not installed (pip install openai)."}
        where = cfg.base_url or "openai"
        model = cfg.model or "gpt-4o-mini"
        try:
            client = OpenAI(api_key=cfg.api_key or "not-needed", base_url=cfg.base_url or None)
            # 1) prefer the model list — validates the model id for free (no tokens)
            try:
                ids = {m.id for m in client.models.list().data}
                if model in ids:
                    return {"provider": provider, "ok": True,
                            "detail": f"Ready ({model} @ {where})."}
            except Exception:
                ids = None   # endpoint has no /models — fall through to a probe
            # 2) model not listed (or no list) — probe with room for reasoning models
            from .llm.openai_provider import chat_completion
            chat_completion(client, model=model, max_out=256,
                            messages=[{"role": "user", "content": "ping"}])
            return {"provider": provider, "ok": True,
                    "detail": f"Ready ({model} @ {where})."}
        except Exception as e:
            return {"provider": provider, "ok": False, "detail": str(e)[:220]}

    return {"provider": provider, "ok": False, "detail": "unknown provider"}


def _run(db: Session, imp: OpenCliImport, brief: dict, *, created_by, module, cfg=None):
    from . import code_service  # lazy: code_service imports models heavily

    cfg = cfg or _resolve(db)
    provider = registry.get(cfg.provider)
    try:
        result = provider.generate(brief, cfg)
    except Exception as e:
        # surface the real provider error (auth/model/network) instead of a 500
        return {
            "import_id": imp.id, "module": module, "provider": cfg.provider,
            "mode": "error", "model": cfg.model, "files": 0,
            "candidate_dir": None, "code_version_id": None, "verify": None,
            "note": f"provider error: {str(e)[:300]}", "brief": None,
        }

    verify = None
    candidate_dir = None
    code_version_id = None
    if result.files:
        try:
            # each generation gets its own dir so old versions stay intact as history
            base = os.path.join(imp.artifact_dir or ".", "code")
            n = 1
            while os.path.exists(os.path.join(base, f"v{n}")):
                n += 1
            candidate_dir = os.path.join(base, f"v{n}")
            root = Path(candidate_dir)
            root.mkdir(parents=True, exist_ok=True)
            for f in result.files:
                dest = (root / f.path).resolve()
                if not str(dest).startswith(str(root.resolve()) + os.sep):
                    continue  # reject path traversal
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(f.content, encoding="utf-8")
            verify = regen.verify_candidate(candidate_dir)
            cv = code_service.record(
                db, imp, code_dir=candidate_dir, provider=result.provider,
                model=result.model, files_count=len(result.files), verify=verify,
                created_by=created_by, module=module,
            )
            code_version_id = cv.id
        except Exception as e:
            db.rollback()
            return {
                "import_id": imp.id, "module": module, "provider": result.provider,
                "mode": "error", "model": result.model, "files": len(result.files),
                "candidate_dir": candidate_dir, "code_version_id": None, "verify": None,
                "note": f"save error: {str(e)[:300]}", "brief": None,
            }

    return {
        "import_id": imp.id, "module": module,
        "provider": result.provider, "mode": result.mode, "model": result.model,
        "files": len(result.files), "candidate_dir": candidate_dir,
        "code_version_id": code_version_id, "verify": verify,
        "note": result.note, "brief": result.brief,
    }


def generate(db: Session, imp: OpenCliImport, *, created_by=None) -> dict:
    """Whole-app generation (one shot). Best for small systems; for real apps use
    generate_module per module."""
    return _run(db, imp, regen.build_brief(imp), created_by=created_by, module=None)


def generate_module(db: Session, imp: OpenCliImport, module: str, *,
                    created_by=None, model_id=None) -> dict:
    """Generate ONE module — scoped, step-by-step. `model_id` picks a specific
    configured AI (multi-agent); omit to use the default provider config."""
    from .modules import build_module_brief
    cfg = None
    if model_id is not None:
        from . import llm_models_service
        cfg = llm_models_service.resolve(db, model_id)
    return _run(db, imp, build_module_brief(imp, module),
                created_by=created_by, module=module, cfg=cfg)
