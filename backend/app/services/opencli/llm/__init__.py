"""Provider-agnostic LLM layer for OpenCLI Bridge regeneration.

Vendor-neutral by design (no lock-in): the default provider makes NO external
call, and the OpenAI-compatible provider can point at a fully on-prem model
(Ollama, vLLM, LM Studio) via base_url. Claude is the recommended default when
configured, never a hard dependency.
"""
