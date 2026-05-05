from __future__ import annotations

from collections.abc import Iterator

import pytest

from triforge import _llm
from triforge._llm import (
    AnthropicProvider,
    LLMProvider,
    Message,
    OllamaProvider,
    OpenAIProvider,
    complete,
    get_provider,
    provider_name,
    reset_provider_cache,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip credentials and force-overrides before each test, restore after."""
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_HOST",
        "TRIFORGE_LLM_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_provider_cache()
    yield
    reset_provider_cache()


def test_no_keys_means_no_provider() -> None:
    assert get_provider() is None
    assert complete([Message(role="user", content="hi")]) is None
    assert provider_name() == "none"


def test_force_none_disables_even_when_creds_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("TRIFORGE_LLM_PROVIDER", "none")
    reset_provider_cache()
    assert get_provider() is None


def test_anthropic_selected_when_only_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    class FakeAnthropic(AnthropicProvider):
        @classmethod
        def is_available(cls) -> bool:
            return True

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {
        "anthropic": FakeAnthropic,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    })
    reset_provider_cache()
    p = get_provider()
    assert p is not None and p.name == "anthropic"


def test_openai_selected_when_only_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    class FakeOpenAI(OpenAIProvider):
        @classmethod
        def is_available(cls) -> bool:
            return True

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {
        "anthropic": AnthropicProvider,
        "openai": FakeOpenAI,
        "ollama": OllamaProvider,
    })
    reset_provider_cache()
    p = get_provider()
    assert p is not None and p.name == "openai"


def test_anthropic_wins_over_openai_when_both_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("OPENAI_API_KEY", "fake")

    class FakeAnthropic(AnthropicProvider):
        @classmethod
        def is_available(cls) -> bool:
            return True

    class FakeOpenAI(OpenAIProvider):
        @classmethod
        def is_available(cls) -> bool:
            return True

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {
        "anthropic": FakeAnthropic,
        "openai": FakeOpenAI,
        "ollama": OllamaProvider,
    })
    reset_provider_cache()
    p = get_provider()
    assert p is not None and p.name == "anthropic"


def test_complete_with_stub_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stub(LLMProvider):
        name = "stub"

        @classmethod
        def is_available(cls) -> bool:
            return True

        def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
            return "OK: " + messages[-1].content

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {"stub": Stub})
    monkeypatch.setenv("TRIFORGE_LLM_PROVIDER", "stub")
    reset_provider_cache()
    out = complete([Message(role="user", content="ping")])
    assert out == "OK: ping"
