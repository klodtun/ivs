"""Natural-language chat (P11) — talk to the bridge in plain language.

Grounds the configured LLM provider with a project's OpenCLI manifest so an
operator can ask questions or request changes in Thai/English. Provider-neutral
(same config as regen); manual mode returns a helpful offline message.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import OpenCliImport, OpenCliImportStatus
from . import reader
from .llm import registry
from .regen_service import _resolve

_SYSTEM = (
    "You are the OpenCLI Bridge assistant. You help a solo operator understand and "
    "evolve a legacy system that has been converted to an OpenCLI manifest. Answer "
    "concisely in the user's language. When asked to add or change a feature, describe "
    "the concrete steps and which commands/entities are affected — do not invent data."
)


def _latest_manifest_for_project(db: Session, project_id: int) -> Optional[list[dict]]:
    imp = (db.query(OpenCliImport)
           .filter(OpenCliImport.project_id == project_id,
                   OpenCliImport.status == OpenCliImportStatus.TRANSFORMED)
           .order_by(OpenCliImport.created_at.desc()).first())
    return reader.read_manifest(imp) if imp else None


def chat(db: Session, *, project_id: Optional[int], message: str) -> dict:
    cfg = _resolve(db)
    manifest = _latest_manifest_for_project(db, project_id) if project_id else None
    context = ("Project commands (OpenCLI manifest):\n"
               + json.dumps(manifest, ensure_ascii=False)[:8000]) if manifest else \
              "No project manifest available."

    if cfg.provider == "manual":
        cmds = len(manifest) if manifest else 0
        return {"provider": "manual", "mode": "offline",
                "reply": (f"Manual mode (no AI provider configured). This project has "
                          f"{cmds} OpenCLI commands. Configure an AI provider "
                          f"(anthropic / openai) to chat and generate changes. "
                          f"Your message: “{message}”")}

    prompt = f"{context}\n\nUser: {message}"

    if cfg.provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=cfg.api_key, base_url=cfg.base_url or None)
        with client.messages.stream(
            model=cfg.model or "claude-opus-4-8", max_tokens=4096,
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            system=_SYSTEM, messages=[{"role": "user", "content": prompt}],
        ) as s:
            msg = s.get_final_message()
        reply = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return {"provider": "anthropic", "mode": "chat", "reply": reply}

    if cfg.provider == "openai":
        from openai import OpenAI
        from .llm.openai_provider import chat_completion
        client = OpenAI(api_key=cfg.api_key or "not-needed", base_url=cfg.base_url or None)
        resp = chat_completion(
            client, model=cfg.model or "gpt-4o-mini", max_out=4096,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": prompt}])
        msg = resp.choices[0].message
        return {"provider": "openai", "mode": "chat",
                "reply": msg.content or getattr(msg, "reasoning_content", "") or ""}

    return {"provider": cfg.provider, "mode": "error", "reply": "unknown provider"}
