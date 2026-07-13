"""Anthropic (Claude) provider — recommended default when a key is configured.

Uses the official `anthropic` SDK. Model defaults to claude-opus-4-8 with adaptive
thinking + high effort, streamed to avoid HTTP timeouts on long output. Lazy
import so the SDK is only required when this provider is actually selected.
"""
from __future__ import annotations

from .base import (
    SYSTEM_PROMPT,
    GenerationResult,
    ProviderConfig,
    build_user_prompt,
    parse_files_safe,
)

DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider:
    name = "anthropic"
    needs_key = True

    def generate(self, brief: dict, cfg: ProviderConfig) -> GenerationResult:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError("anthropic SDK not installed (pip install anthropic)") from e
        if not cfg.api_key:
            raise RuntimeError("anthropic provider requires an API key")

        client = anthropic.Anthropic(api_key=cfg.api_key,
                                     base_url=cfg.base_url or None)
        model = cfg.model or DEFAULT_MODEL

        with client.messages.stream(
            model=model,
            max_tokens=64000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(brief)}],
        ) as stream:
            msg = stream.get_final_message()

        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        files, note = parse_files_safe(text)
        return GenerationResult(
            provider=self.name, mode="generated", model=model, files=files,
            note=f"{note} · {model}",
        )
