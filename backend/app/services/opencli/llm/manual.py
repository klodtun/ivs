"""Manual provider (default) — no LLM call.

Returns the generation brief for an external agent (Claude Code / Cursor via the
MCP server). This is the zero-dependency, zero-cost, no-vendor-lock baseline: the
Bridge works with no API key and no external provider configured.
"""
from __future__ import annotations

from .base import GenerationResult, ProviderConfig


class ManualProvider:
    name = "manual"
    needs_key = False

    def generate(self, brief: dict, cfg: ProviderConfig) -> GenerationResult:
        return GenerationResult(
            provider=self.name,
            mode="manual",
            brief=brief,
            note=("No LLM provider configured. Feed this brief to an external agent "
                  "via the MCP server (tools: get_manifest / get_structure), or "
                  "configure a provider (anthropic / openai-compatible) to generate "
                  "code in-app."),
        )
