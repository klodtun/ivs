"""LLM provider interface + shared types for regeneration."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


@dataclass
class GeneratedFile:
    path: str                 # relative path inside the app (e.g. "backend/main.py")
    content: str


@dataclass
class GenerationResult:
    provider: str
    mode: str                 # "manual" (brief only) | "generated" (files)
    model: Optional[str] = None
    files: list[GeneratedFile] = field(default_factory=list)
    note: str = ""
    brief: Optional[dict] = None   # populated in manual mode for an external agent


@dataclass
class ProviderConfig:
    provider: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None   # decrypted at call time; never logged


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    needs_key: bool

    def generate(self, brief: dict, cfg: ProviderConfig) -> GenerationResult:
        ...


# Shared system prompt for code-generating providers. Kept provider-neutral so
# swapping models doesn't change the contract.
SYSTEM_PROMPT = (
    "You regenerate a runnable application from an OpenCLI Bridge brief.\n"
    "The brief contains a cli-manifest (commands), a structure markdown (entities "
    "and non-PII columns), and a target zip layout that the IVS deploy path accepts.\n"
    "Output ONLY a JSON array of files: [{\"path\": \"<relative path>\", "
    "\"content\": \"<file text>\"}]. No prose, no markdown fences.\n"
    "Produce the smallest app that satisfies the manifest and would pass "
    "structural validation for its app type. Never include PII columns that the "
    "brief omitted."
)


def build_user_prompt(brief: dict) -> str:
    return (
        "Regenerate the system described by this brief.\n\n"
        + json.dumps(brief, ensure_ascii=False, indent=2)
    )


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_files_safe(text: str) -> tuple[list[GeneratedFile], str]:
    """Parse; never raise. Returns (files, note). On failure files=[] and note
    carries a snippet of what the model actually said, so the UI isn't silent."""
    try:
        files = parse_files(text)
    except Exception:
        files = []
    if not files:
        snippet = (text or "").strip().replace("\n", " ")[:400]
        return [], f"model did not return a parseable file set. Model said: {snippet}"
    return files, f"generated {len(files)} files"


def parse_files(text: str) -> list[GeneratedFile]:
    """Tolerant parse of a model's file output. Accepts, in order of preference:
    a JSON array `[{path,content}]`, a `{"files":[...]}` wrapper, or a single
    object `{path,content}` (small models often return one file unwrapped)."""
    cleaned = _FENCE.sub("", text).strip()
    data = None
    # try the whole thing first (array or object)
    try:
        data = json.loads(cleaned)
    except Exception:
        # else slice out the first bracketed JSON (array preferred, then object)
        for lo, hi in (("[", "]"), ("{", "}")):
            s, e = cleaned.find(lo), cleaned.rfind(hi)
            if s != -1 and e != -1 and e > s:
                try:
                    data = json.loads(cleaned[s:e + 1])
                    break
                except Exception:
                    continue
    if data is None:
        return []
    # normalize to a list of {path,content} dicts
    if isinstance(data, dict):
        items = data["files"] if isinstance(data.get("files"), list) else [data]
    elif isinstance(data, list):
        items = data
    else:
        return []
    out: list[GeneratedFile] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        p = str(item.get("path", "")).lstrip("/")
        if p and "content" in item:
            out.append(GeneratedFile(path=p, content=str(item["content"])))
    return out
