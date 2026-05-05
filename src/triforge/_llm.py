"""Auto-fallback LLM provider chain.

Order:
    1. Anthropic   — uses ``ANTHROPIC_API_KEY`` (model: claude-haiku-4-5)
    2. OpenAI      — uses ``OPENAI_API_KEY``    (model: gpt-4o-mini)
    3. Ollama      — uses ``OLLAMA_HOST``       (model: qwen2.5:7b or any preset)
    4. None        — caller must handle (dense-only fallback)

The chain is environment-driven: whichever provider has its credential
available first wins. Override with ``TRIFORGE_LLM_PROVIDER=anthropic|openai|ollama|none``.

Provider-specific deps live in the optional ``[llm]`` extra of triforge.
A missing import does not crash — it just disqualifies that provider.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


class LLMUnavailableError(RuntimeError):
    """Raised when no provider can be selected (or selected one has no creds)."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str: ...

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool: ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    default_model = os.environ.get("TRIFORGE_ANTHROPIC_MODEL", "claude-haiku-4-5")

    @classmethod
    def is_available(cls) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
        import anthropic

        client = anthropic.Anthropic()
        sys_msgs = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        kwargs: dict = {
            "model": self.default_model,
            "max_tokens": max_tokens,
            "messages": chat,
        }
        if sys_msgs:
            kwargs["system"] = "\n\n".join(sys_msgs)
        resp = client.messages.create(**kwargs)
        parts = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    name = "openai"
    default_model = os.environ.get("TRIFORGE_OPENAI_MODEL", "gpt-4o-mini")

    @classmethod
    def is_available(cls) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
        import openai

        client = openai.OpenAI()
        chat = [{"role": m.role, "content": m.content} for m in messages]
        resp = client.chat.completions.create(
            model=self.default_model,
            messages=chat,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Ollama (HTTP)
# ---------------------------------------------------------------------------


class OllamaProvider(LLMProvider):
    name = "ollama"
    default_model = os.environ.get("TRIFORGE_OLLAMA_MODEL", "qwen2.5:7b")

    @classmethod
    def host(cls) -> str:
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

    @classmethod
    def is_available(cls) -> bool:
        try:
            import httpx
        except ImportError:
            return False
        try:
            r = httpx.get(f"{cls.host()}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
        import httpx

        chat = [{"role": m.role, "content": m.content} for m in messages]
        r = httpx.post(
            f"{self.host()}/api/chat",
            json={
                "model": self.default_model,
                "messages": chat,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=60.0,
        )
        r.raise_for_status()
        return (r.json().get("message", {}).get("content") or "").strip()


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

_PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def _override() -> str | None:
    raw = os.environ.get("TRIFORGE_LLM_PROVIDER", "").strip().lower() or None
    if raw == "none":
        return "none"
    return raw


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider | None:
    """Return the highest-priority available provider, or ``None``."""
    forced = _override()
    if forced == "none":
        return None
    if forced and forced in _PROVIDER_CLASSES:
        cls = _PROVIDER_CLASSES[forced]
        if cls.is_available():
            return cls()
        return None
    for name in ("anthropic", "openai", "ollama"):
        cls = _PROVIDER_CLASSES[name]
        if cls.is_available():
            return cls()
    return None


def reset_provider_cache() -> None:
    """Reset the cached selection (used by tests when env vars change)."""
    get_provider.cache_clear()


def complete(messages: list[Message], *, max_tokens: int = 512) -> str | None:
    """Convenience: complete with the auto-selected provider; ``None`` if no provider."""
    p = get_provider()
    if p is None:
        return None
    return p.complete(messages, max_tokens=max_tokens)


def provider_name() -> str:
    p = get_provider()
    return p.name if p else "none"
