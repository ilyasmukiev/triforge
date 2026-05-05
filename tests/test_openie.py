from __future__ import annotations

from collections.abc import Iterator

import pytest

from triforge import _llm
from triforge._llm import LLMProvider, Message, reset_provider_cache
from triforge.memory.openie import Triplet, _safe_json_array, extract_triplets


@pytest.fixture(autouse=True)
def _isolate_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TRIFORGE_LLM_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    reset_provider_cache()
    yield
    reset_provider_cache()


def test_no_provider_returns_empty_triplets() -> None:
    assert extract_triplets("Some text about Flask sessions.") == []


def test_safe_json_array_strips_fences() -> None:
    assert _safe_json_array('```json\n[{"subject":"a","relation":"b","object":"c"}]\n```') == [
        {"subject": "a", "relation": "b", "object": "c"}
    ]


def test_safe_json_array_returns_empty_on_garbage() -> None:
    assert _safe_json_array("no json here") == []


def test_extract_with_stub_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stub(LLMProvider):
        name = "stub"

        @classmethod
        def is_available(cls) -> bool:
            return True

        def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
            return (
                '[{"subject":"Flask","relation":"uses","object":"sessions"},'
                ' {"subject":"sessions","relation":"signed_with","object":"SECRET_KEY"}]'
            )

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {"stub": Stub})
    monkeypatch.setenv("TRIFORGE_LLM_PROVIDER", "stub")
    reset_provider_cache()
    out = extract_triplets("Flask uses sessions signed with SECRET_KEY.")
    assert len(out) == 2
    assert out[0] == Triplet("Flask", "uses", "sessions")


def test_extract_skips_short_text() -> None:
    assert extract_triplets("hi") == []
    assert extract_triplets("") == []


def test_extract_caps_per_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stub(LLMProvider):
        name = "stub"

        @classmethod
        def is_available(cls) -> bool:
            return True

        def complete(self, messages: list[Message], *, max_tokens: int = 512) -> str:
            many = [
                {"subject": f"s{i}", "relation": "r", "object": f"o{i}"}
                for i in range(20)
            ]
            import json

            return json.dumps(many)

    monkeypatch.setattr(_llm, "_PROVIDER_CLASSES", {"stub": Stub})
    monkeypatch.setenv("TRIFORGE_LLM_PROVIDER", "stub")
    reset_provider_cache()
    out = extract_triplets("a real sentence with several entities", max_per_chunk=3)
    assert len(out) == 3
