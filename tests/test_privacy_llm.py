from __future__ import annotations

from collections.abc import Iterator

import pytest

from triforge import _llm
from triforge._llm import LLMProvider, Message, reset_provider_cache
from triforge._privacy_llm import clean_if_needed, llm_clean, needs_cleaning


@pytest.fixture(autouse=True)
def _isolate_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TRIFORGE_LLM_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    reset_provider_cache()
    yield
    reset_provider_cache()


def test_needs_cleaning_detects_trigger_words() -> None:
    assert needs_cleaning("here is my password: foo")
    assert needs_cleaning("Bearer abc.def.ghi")
    assert needs_cleaning("an API_KEY=xyz")


def test_needs_cleaning_skips_clean_text() -> None:
    assert not needs_cleaning("Just normal conversation about Python.")
    assert not needs_cleaning("")


def test_no_provider_returns_text_unchanged() -> None:
    src = "I think the password is hunter2"
    assert llm_clean(src) == src
    assert clean_if_needed(src) == src


def test_clean_if_needed_short_circuits_clean_text() -> None:
    src = "Tell me about the architecture diagram."
    assert clean_if_needed(src) == src  # no trigger word → returns as-is


def test_llm_clean_with_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stub(LLMProvider):
        name = "stub"

        @classmethod
        def is_available(cls) -> bool:
            return True

        def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
            user_text = messages[-1].content
            # crude: pretend we redacted any token-like chunk
            return user_text.replace("hunter2", "[REDACTED]")

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {"stub": Stub})
    monkeypatch.setenv("TRIFORGE_LLM_PROVIDER", "stub")
    reset_provider_cache()
    out = clean_if_needed("password is hunter2 and that is bad")
    assert "hunter2" not in out
    assert "[REDACTED]" in out
