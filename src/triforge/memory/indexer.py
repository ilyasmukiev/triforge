"""Background indexer: turn unindexed chats.jsonl entries into vectors + summary."""
from __future__ import annotations
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from triforge._config import is_project_activated
from triforge._embedder import embed_batch
from triforge._hashing import project_hash
from triforge.memory.store import (
    ChatRecord,
    VectorRecord,
    append_summary,
    append_vectors,
    iter_unindexed_chats,
    mark_indexed,
)


def _chunk_id(rec: ChatRecord) -> str:
    h = hashlib.sha256(
        f"{rec.session_id}|{rec.ts}|{rec.role}|{rec.text}".encode("utf-8")
    )
    return h.hexdigest()[:16]


def _summary_for(records: list[ChatRecord]) -> str:
    """MVP summary: header + the first 200 chars of each user message.

    Plan 2 will replace this with an LLM-generated summary using the
    auto-fallback chain.
    """
    if not records:
        return ""
    sid = records[0].session_id
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    user_lines = [r.text[:200] for r in records if r.role == "user"]
    body = "\n".join(f"- {line}" for line in user_lines) or "- (no user messages)"
    return f"## Session {sid} — {when}\n{body}"


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
    append_summary(h, _summary_for(records))
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
