"""OpenAI-compatible provider — the anti-lock-in path.

The OpenAI chat-completions API shape is a de-facto standard, so ONE provider
class covers OpenAI, Azure OpenAI, and — crucially for on-prem / government
deployments — local runtimes (Ollama, vLLM, LM Studio, LocalAI) via `base_url`.
Point base_url at http://localhost:11434/v1 (Ollama) to run fully offline with
no external vendor.

Lazy import of the `openai` SDK so it's only required when selected.
"""
from __future__ import annotations

from .base import (
    SYSTEM_PROMPT,
    GenerationResult,
    ProviderConfig,
    build_user_prompt,
    parse_files_safe,
)

DEFAULT_MODEL = "gpt-4o-mini"  # overridden by config; local users set e.g. "llama3.1"


def chat_completion(client, *, model, messages, max_out=8192):
    """OpenAI-compatible chat call that works across old and new models: older
    models take `max_tokens`, newer ones (gpt-5/o-series) require
    `max_completion_tokens`. Try one, fall back on the specific 400."""
    try:
        return client.chat.completions.create(
            model=model, max_tokens=max_out, messages=messages)
    except Exception as e:
        if "max_completion_tokens" in str(e):
            return client.chat.completions.create(
                model=model, max_completion_tokens=max_out, messages=messages)
        raise


class OpenAICompatibleProvider:
    name = "openai"
    needs_key = True  # local runtimes accept any placeholder key

    def generate(self, brief: dict, cfg: ProviderConfig) -> GenerationResult:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai SDK not installed (pip install openai)") from e

        # Local runtimes ignore the key but the SDK requires a non-empty string.
        client = OpenAI(api_key=cfg.api_key or "not-needed",
                        base_url=cfg.base_url or None)
        model = cfg.model or DEFAULT_MODEL

        resp = chat_completion(
            client, model=model, max_out=8192,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(brief)},
            ],
        )
        msg = resp.choices[0].message
        # some OpenAI-compatible endpoints (e.g. NVIDIA reasoning models) split the
        # answer into content vs reasoning_content — prefer content, fall back.
        text = msg.content or getattr(msg, "reasoning_content", "") or ""
        files, note = parse_files_safe(text)
        return GenerationResult(
            provider=self.name, mode="generated", model=model, files=files,
            note=f"{note} · {model} @ {cfg.base_url or 'openai'}",
        )
