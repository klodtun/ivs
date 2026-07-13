"""Provider registry — resolve a provider by name."""
from __future__ import annotations

from .base import LLMProvider
from .manual import ManualProvider
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAICompatibleProvider

_PROVIDERS: dict[str, LLMProvider] = {
    p.name: p for p in (ManualProvider(), AnthropicProvider(), OpenAICompatibleProvider())
}

DEFAULT_PROVIDER = "manual"   # zero-dependency, no external call, no lock-in


def available() -> list[dict]:
    return [{"name": p.name, "needs_key": p.needs_key} for p in _PROVIDERS.values()]


def get(name: str) -> LLMProvider:
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(f"unknown LLM provider: {name!r} (have {list(_PROVIDERS)})")
