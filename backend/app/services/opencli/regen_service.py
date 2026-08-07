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


import re as _re

# human-readable meaning for the common HTTP / pipeline error codes
_ERR_EXPLAIN = {
    "400": "คำขอไม่ถูกต้อง — มักเป็นพารามิเตอร์ผิด (เช่น max_tokens ไม่รองรับในโมเดล reasoning)",
    "401": "คีย์ API ไม่ถูกต้อง/หมดอายุ — ตรวจ Vault key",
    "403": "ไม่มีสิทธิ์เข้าถึงโมเดลนี้ด้วยคีย์ปัจจุบัน",
    "404": "ไม่พบโมเดล — ชื่อโมเดลผิด (เช่นใส่ prefix ซ้ำ)",
    "408": "หมดเวลา — โมเดลตอบช้าเกินไป",
    "422": "โมเดลไม่รับรูปแบบคำขอ",
    "428": "โมเดลต้องการเงื่อนไขก่อน (Precondition) — มักคือ context/โควตา/ต้องยืนยันก่อนใช้",
    "429": "เรียกถี่เกินโควตา (rate limit) — รอสักครู่หรือสลับโมเดล",
    "500": "โมเดล/เซิร์ฟเวอร์ผู้ให้บริการ error ภายใน — ลองใหม่หรือสลับ AI",
    "502": "เกตเวย์ผู้ให้บริการล่ม",
    "503": "บริการโมเดลไม่พร้อม (overloaded) — สลับ AI",
    "504": "เกตเวย์หมดเวลา",
    "parse": "โมเดลตอบไม่ใช่ JSON ไฟล์ที่อ่านได้ — โมเดลเล็ก/ไม่ทำตามรูปแบบ ลองโมเดลเก่งกว่า",
    "save": "สร้างไฟล์ได้แต่เขียนลงดิสก์ไม่สำเร็จ",
    "provider": "เรียกผู้ให้บริการไม่สำเร็จ (network/auth)",
}


def _error_code(note: Optional[str]) -> Optional[str]:
    """Extract a short error code from a provider note string."""
    if not note:
        return None
    m = _re.search(r"\b(4\d\d|5\d\d)\b", note)
    if m:
        return m.group(1)
    low = note.lower()
    if "save error" in low:
        return "save"
    if "parse" in low or "no files" in low or "files=0" in low:
        return "parse"
    if "provider error" in low:
        return "provider"
    return None


def _log_attempt(db: Session, imp: OpenCliImport, module, result: dict,
                 *, model_id, created_by) -> None:
    """Persist a generation attempt (success or error) for later review."""
    from app.models import OpenCliGenAttempt
    ok = result.get("files", 0) > 0 and result.get("mode") != "error"
    code = None if ok else _error_code(result.get("note"))
    try:
        db.add(OpenCliGenAttempt(
            project_id=imp.project_id or None, import_id=imp.id, module=module,
            provider=result.get("provider"), model=result.get("model"),
            model_id=model_id, ok=ok, files=result.get("files", 0),
            error_code=code,
            note=((_ERR_EXPLAIN.get(code) + " — ") if code and _ERR_EXPLAIN.get(code) else "")
                 + (result.get("note") or "")[:400] if not ok else (result.get("note") or "")[:200],
            created_by=created_by,
        ))
        db.commit()
    except Exception:
        db.rollback()  # logging must never break generation


def _run(db: Session, imp: OpenCliImport, brief: dict, *, created_by, module,
         cfg=None, model_id=None):
    from . import code_service  # lazy: code_service imports models heavily

    cfg = cfg or _resolve(db)
    provider = registry.get(cfg.provider)
    try:
        result = provider.generate(brief, cfg)
    except Exception as e:
        # surface the real provider error (auth/model/network) instead of a 500
        r = {
            "import_id": imp.id, "module": module, "provider": cfg.provider,
            "mode": "error", "model": cfg.model, "files": 0,
            "candidate_dir": None, "code_version_id": None, "verify": None,
            "note": f"provider error: {str(e)[:300]}", "brief": None,
        }
        _log_attempt(db, imp, module, r, model_id=model_id, created_by=created_by)
        return r

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
            r = {
                "import_id": imp.id, "module": module, "provider": result.provider,
                "mode": "error", "model": result.model, "files": len(result.files),
                "candidate_dir": candidate_dir, "code_version_id": None, "verify": None,
                "note": f"save error: {str(e)[:300]}", "brief": None,
            }
            _log_attempt(db, imp, module, r, model_id=model_id, created_by=created_by)
            return r

    r = {
        "import_id": imp.id, "module": module,
        "provider": result.provider, "mode": result.mode, "model": result.model,
        "files": len(result.files), "candidate_dir": candidate_dir,
        "code_version_id": code_version_id, "verify": verify,
        "note": result.note, "brief": result.brief,
    }
    _log_attempt(db, imp, module, r, model_id=model_id, created_by=created_by)
    return r


def list_attempts(db: Session, *, project_id=None, import_id=None,
                  limit: int = 100) -> list[dict]:
    """Recent generation attempts (newest first) for a project or import.
    Powers the error-history dropdown so operators pick a better AI."""
    from app.models import OpenCliGenAttempt
    q = db.query(OpenCliGenAttempt)
    if project_id is not None:
        q = q.filter(OpenCliGenAttempt.project_id == project_id)
    if import_id is not None:
        q = q.filter(OpenCliGenAttempt.import_id == import_id)
    rows = q.order_by(OpenCliGenAttempt.created_at.desc()).limit(limit).all()
    return [{
        "id": a.id, "module": a.module, "provider": a.provider, "model": a.model,
        "model_id": a.model_id, "ok": a.ok, "files": a.files,
        "error_code": a.error_code, "note": a.note,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in rows]


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
                created_by=created_by, module=module, cfg=cfg, model_id=model_id)
