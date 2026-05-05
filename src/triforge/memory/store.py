"""Per-project chat-memory store: chats.jsonl + state.json + vectors/ + summary.md."""
from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from triforge._locking import (
    append_locked,
    read_json_locked,
    read_text_locked,
    write_json_locked,
)
from triforge._paths import chats_jsonl, state_json, summary_md, vectors_dir


@dataclass
class ChatRecord:
    ts: str
    session_id: str
    role: Literal["user", "assistant"]
    text: str


@dataclass
class VectorRecord:
    chunk_id: str
    text: str
    role: Literal["user", "assistant"]
    session_id: str
    ts: str
    vector: np.ndarray  # shape (EMBED_DIM,), float32


def append_chat(project_hash: str, record: ChatRecord) -> None:
    line = json.dumps(asdict(record), ensure_ascii=False) + "\n"
    append_locked(chats_jsonl(project_hash), line)


def _state(project_hash: str) -> dict:
    return read_json_locked(state_json(project_hash), default={"last_indexed_offset": 0})


def iter_unindexed_chats(project_hash: str) -> Iterator[ChatRecord]:
    p = chats_jsonl(project_hash)
    if not p.exists():
        return
    state = _state(project_hash)
    offset = state.get("last_indexed_offset", 0)
    text = read_text_locked(p)
    if offset >= len(text):
        return
    for line in text[offset:].splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        yield ChatRecord(**d)


def mark_indexed(project_hash: str) -> None:
    text = read_text_locked(chats_jsonl(project_hash))
    write_json_locked(state_json(project_hash), {"last_indexed_offset": len(text)})


def append_summary(project_hash: str, body: str) -> None:
    append_locked(summary_md(project_hash), body.rstrip("\n") + "\n\n")


def read_summary_tail(project_hash: str, max_chars: int = 3500) -> str:
    text = read_text_locked(summary_md(project_hash))
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _next_shard_path(project_hash: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return vectors_dir(project_hash) / f"{ts}.parquet"


def append_vectors(project_hash: str, records: Sequence[VectorRecord]) -> None:
    if not records:
        return
    table = pa.table(
        {
            "chunk_id":   [r.chunk_id   for r in records],
            "text":       [r.text       for r in records],
            "role":       [r.role       for r in records],
            "session_id": [r.session_id for r in records],
            "ts":         [r.ts         for r in records],
            "vector":     [r.vector.tolist() for r in records],
        }
    )
    pq.write_table(table, _next_shard_path(project_hash))


def load_all_vectors(project_hash: str) -> list[VectorRecord]:
    out: list[VectorRecord] = []
    for shard in sorted(vectors_dir(project_hash).glob("*.parquet")):
        t = pq.read_table(shard)
        for i in range(t.num_rows):
            out.append(
                VectorRecord(
                    chunk_id=t["chunk_id"][i].as_py(),
                    text=t["text"][i].as_py(),
                    role=t["role"][i].as_py(),
                    session_id=t["session_id"][i].as_py(),
                    ts=t["ts"][i].as_py(),
                    vector=np.array(t["vector"][i].as_py(), dtype=np.float32),
                )
            )
    return out
