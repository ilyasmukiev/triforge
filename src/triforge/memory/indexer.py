"""Background indexer.

Pipeline per ``run_index_once``:
    1. Pull unindexed records from chats.jsonl.
    2. Dense embeddings via model2vec → parquet shard.
    3. Optional: LLM summary (if a provider is available).
    4. Optional: OpenIE triplets → NetworkX knowledge graph.
    5. Append a header line to summary.md and persist state.

If no LLM provider is configured, steps 3 and 4 are skipped — the
fallback is a deterministic header + first-200-chars-per-user-message
recap. Either way, dense + BM25 search keeps working.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from triforge._config import is_project_activated
from triforge._embedder import embed_batch
from triforge._hashing import project_hash
from triforge._llm import Message, complete, get_provider
from triforge.memory.graph import index_chunks_into_graph
from triforge.memory.openie import extract_triplets
from triforge.memory.store import (
    ChatRecord,
    VectorRecord,
    append_summary,
    append_vectors,
    iter_unindexed_chats,
    mark_indexed,
)

SUMMARY_SYSTEM = (
    "You are a project-memory summarizer. Read the recent user/assistant exchange "
    "from a coding session and produce a SHORT bullet list (max 6 bullets, "
    "≤ 25 words each). Focus on: decisions made, files changed, problems unsolved, "
    "next steps. NO greetings, NO restating the question. Reply with bullets only."
)


def _chunk_id(rec: ChatRecord) -> str:
    h = hashlib.sha256(
        f"{rec.session_id}|{rec.ts}|{rec.role}|{rec.text}".encode()
    )
    return h.hexdigest()[:16]


def _deterministic_summary(records: list[ChatRecord]) -> str:
    user_lines = [r.text[:200] for r in records if r.role == "user"]
    return "\n".join(f"- {line}" for line in user_lines) or "- (no user messages)"


def _llm_summary(records: list[ChatRecord]) -> str | None:
    """One LLM round-trip; returns ``None`` if no provider or empty response."""
    if get_provider() is None:
        return None
    transcript = "\n".join(
        f"[{r.role}] {r.text[:600]}" for r in records[-30:]
    )
    msgs = [
        Message(role="system", content=SUMMARY_SYSTEM),
        Message(role="user", content=transcript),
    ]
    try:
        out = complete(msgs, max_tokens=300)
    except Exception:
        return None
    if not out:
        return None
    return out.strip()


def _summary_block(records: list[ChatRecord]) -> str:
    if not records:
        return ""
    sid = records[0].session_id
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = _llm_summary(records) or _deterministic_summary(records)
    return f"## Session {sid} — {when}\n{body}"


def _build_graph(project_hash_: str, vec_records: list[VectorRecord]) -> int:
    """Run OpenIE on each chunk and add triplets to the project graph.

    Returns the number of triplets added (0 if no LLM provider).
    """
    if get_provider() is None:
        return 0
    chunks: list[tuple[str, list]] = []
    for vr in vec_records:
        triplets = extract_triplets(vr.text)
        if triplets:
            chunks.append((vr.chunk_id, triplets))
    if not chunks:
        return 0
    _, n_triplets = index_chunks_into_graph(project_hash_, chunks)
    return n_triplets


def run_index_once(project: Path) -> int:
    """Index any new chats.jsonl entries for the project. Returns count indexed."""
    if not is_project_activated(project):
        return 0
    h = project_hash(project)
    records = list(iter_unindexed_chats(h))
    if not records:
        return 0

    vectors = embed_batch([r.text for r in records])
    vec_records = [
        VectorRecord(
            chunk_id=_chunk_id(r),
            text=r.text,
            role=r.role,
            session_id=r.session_id,
            ts=r.ts,
            vector=vectors[i],
        )
        for i, r in enumerate(records)
    ]
    append_vectors(h, vec_records)
    append_summary(h, _summary_block(records))
    _build_graph(h, vec_records)
    mark_indexed(h)
    return len(records)


def _detach_kwargs() -> dict:
    if sys.platform == "win32":
        DETACHED = 0x00000008  # subprocess.DETACHED_PROCESS
        NEW_GROUP = 0x00000200  # subprocess.CREATE_NEW_PROCESS_GROUP
        return {"creationflags": DETACHED | NEW_GROUP, "close_fds": True}
    return {"start_new_session": True, "close_fds": True}


def spawn_index_background(project: Path) -> None:
    """Fire-and-forget: re-invoke ourselves in foreground mode and detach."""
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "triforge.cli",
            "index",
            "--project",
            str(project),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **_detach_kwargs(),
    )
