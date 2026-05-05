"""LLM-driven OpenIE: turn a chat chunk into (subject, relation, object) triplets.

Inspired by HippoRAG 2 (OSU NLP Group, Apache-2.0) — instead of depending
on the upstream package (which has heavy ML deps and Python-version churn),
we ask our auto-fallback LLM provider to extract triplets directly. Same
shape, much lighter, fully optional (no provider → no triplets).
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

from triforge._llm import Message, complete

OPENIE_SYSTEM = (
    "You extract knowledge triplets from a single short text. "
    "Return ONLY a JSON array; each item has keys 'subject', 'relation', 'object'. "
    "Keep entities short (≤ 4 words). Skip filler, greetings, code listings. "
    "If nothing meaningful — return []."
)


@dataclass(frozen=True)
class Triplet:
    subject: str
    relation: str
    object: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.subject, self.relation, self.object)


def _safe_json_array(text: str) -> list[dict]:
    """Best-effort: pull the first JSON array out of an LLM response."""
    text = text.strip()
    # strip ```json fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # find the first [...] block
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def extract_triplets(text: str, *, max_per_chunk: int = 6) -> list[Triplet]:
    """Use the auto-fallback LLM to extract up to ``max_per_chunk`` triplets.

    Returns ``[]`` if no LLM provider is available, the response is empty,
    or the JSON cannot be parsed. Never raises — graph indexing must
    degrade gracefully to dense-only.
    """
    text = text.strip()
    if not text or len(text) < 10:
        return []
    msgs = [
        Message(role="system", content=OPENIE_SYSTEM),
        Message(role="user", content=f"Extract triplets from: {text!r}"),
    ]
    try:
        out = complete(msgs, max_tokens=400)
    except Exception:
        return []
    if not out:
        return []
    items = _safe_json_array(out)
    triplets: list[Triplet] = []
    for it in items[:max_per_chunk]:
        if not isinstance(it, dict):
            continue
        s = str(it.get("subject", "")).strip()
        r = str(it.get("relation", "")).strip()
        o = str(it.get("object", "")).strip()
        if s and r and o and all(len(x) <= 80 for x in (s, r, o)):
            triplets.append(Triplet(subject=s, relation=r, object=o))
    return triplets


def extract_many(texts: Iterable[str]) -> list[list[Triplet]]:
    """Batch helper: extract triplets for each text (sequential; one LLM call each)."""
    return [extract_triplets(t) for t in texts]
