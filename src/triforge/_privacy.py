"""Regex first-pass redactor for sensitive strings."""
from __future__ import annotations
import re
from typing import Iterable

REPLACEMENT = "[REDACTED]"

BUILTIN_PATTERNS: list[tuple[str, str]] = [
    (
        "env_var_secret",
        r"\b(?:[A-Z][A-Z0-9_]{2,}_(?:KEY|TOKEN|SECRET|PASSWORD|PWD|API))\s*=\s*\S+",
    ),
    ("bearer_token", r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}"),
    (
        "password_assignment",
        r"(?i)\bpassword\b\s*[:=]\s*[\"']?[^\s\"']{4,}[\"']?",
    ),
    ("jwt", r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ("openai_secret", r"\bsk-[A-Za-z0-9]{20,}"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
    (
        "private_key_block",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
    ),
]


def _compile(patterns: Iterable[tuple[str, str]]) -> list[re.Pattern[str]]:
    return [re.compile(p) for _, p in patterns]


_BUILTIN = _compile(BUILTIN_PATTERNS)


def redact(text: str, extra_patterns: list[str] | None = None) -> str:
    """Replace secrets / tokens / keys in ``text`` with ``[REDACTED]``."""
    out = text
    for pat in _BUILTIN:
        out = pat.sub(REPLACEMENT, out)
    if extra_patterns:
        for raw in extra_patterns:
            out = re.sub(raw, REPLACEMENT, out)
    return out
