"""OpenCLI Bridge — read legacy systems, strip PII, emit OpenCLI artifacts.

Pro/Enterprise feature. See docs/opencli-bridge-architecture.md.
Invariant: raw legacy data never persists — only metadata + SHA-256 hash.
"""
