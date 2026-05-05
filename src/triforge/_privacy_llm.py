"""Heuristic-triggered LLM-cleaner subagent (Plan 2 privacy hardening).

Flow inside ``capture``::

    text → regex first-pass (`_privacy.redact`)
         → if any heuristic trigger word remains
         → LLM cleaner subagent: "redact further; reply with cleaned text only"
         → final text into chats.jsonl

If no LLM provider is configured, the heuristic step is skipped (we keep the
regex output). Never raises; degrades quietly.
"""
from __future__ import annotations

from triforge._llm import Message, complete

TRIGGER_WORDS: tuple[str, ...] = (
    "secret", "password", "passwd", "token", "auth", "api_key", "apikey",
    "private_key", "private key", "bearer", "credential", "ssh-",
)

CLEANER_SYSTEM = (
    "You are a privacy filter. Read the user's text. "
    "Replace any remaining secrets, passwords, API tokens, private keys, "
    "personal addresses, credit card numbers or similar sensitive strings "
    "with the literal text [REDACTED]. "
    "Preserve everything else verbatim. "
    "Reply with ONLY the cleaned text — no preamble, no quoting, no explanation."
)


def needs_cleaning(text: str) -> bool:
    """Cheap heuristic: if any trigger word appears, escalate to LLM."""
    low = text.lower()
    return any(w in low for w in TRIGGER_WORDS)


def llm_clean(text: str, *, max_tokens: int = 1024) -> str:
    """Single LLM round-trip; returns cleaned text or the original if no LLM/error."""
    if not text:
        return text
    msgs = [
        Message(role="system", content=CLEANER_SYSTEM),
        Message(role="user", content=text),
    ]
    try:
        out = complete(msgs, max_tokens=max_tokens)
    except Exception:
        return text
    if not out:
        return text
    return out


def clean_if_needed(text: str) -> str:
    """First-class entry point used by ``capture``: skip work when there's nothing to clean."""
    if not needs_cleaning(text):
        return text
    return llm_clean(text)
