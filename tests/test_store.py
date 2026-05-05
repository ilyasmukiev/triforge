from __future__ import annotations

from pathlib import Path

import numpy as np

from triforge._paths import vectors_dir
from triforge.memory.store import (
    ChatRecord,
    VectorRecord,
    append_chat,
    append_summary,
    append_vectors,
    iter_unindexed_chats,
    load_all_vectors,
    mark_indexed,
    read_summary_tail,
)


def test_append_then_iter_unindexed(tmp_home: Path) -> None:
    h = "abc123"
    r1 = ChatRecord(ts="2026-05-05T12:00:00Z", session_id="s1", role="user", text="hi")
    r2 = ChatRecord(ts="2026-05-05T12:00:01Z", session_id="s1", role="assistant", text="hello")
    append_chat(h, r1)
    append_chat(h, r2)

    new = list(iter_unindexed_chats(h))
    assert [r.text for r in new] == ["hi", "hello"]


def test_mark_indexed_advances_offset(tmp_home: Path) -> None:
    h = "abc456"
    append_chat(h, ChatRecord(ts="t1", session_id="s", role="user", text="a"))
    append_chat(h, ChatRecord(ts="t2", session_id="s", role="assistant", text="b"))
    assert len(list(iter_unindexed_chats(h))) == 2

    mark_indexed(h)
    assert list(iter_unindexed_chats(h)) == []

    append_chat(h, ChatRecord(ts="t3", session_id="s", role="user", text="c"))
    fresh = list(iter_unindexed_chats(h))
    assert [r.text for r in fresh] == ["c"]


def test_append_and_read_summary(tmp_home: Path) -> None:
    h = "abc789"
    append_summary(h, "First session.")
    append_summary(h, "Second session.")
    body = read_summary_tail(h, max_chars=10_000)
    assert "First session." in body
    assert "Second session." in body


def test_read_summary_tail_truncates(tmp_home: Path) -> None:
    h = "abcXYZ"
    append_summary(h, "x" * 5_000)
    append_summary(h, "y" * 5_000)
    tail = read_summary_tail(h, max_chars=3_000)
    assert len(tail) <= 3_000
    # Last appended block ends with "yyy...\n\n", so the tail must contain
    # only y's (and trailing newlines), no x's.
    assert "x" not in tail
    assert tail.count("y") >= 2_900


def test_append_and_load_vectors(tmp_home: Path) -> None:
    h = "vec-abc"
    recs = [
        VectorRecord(
            chunk_id="c1", text="hi", role="user", session_id="s1", ts="t1",
            vector=np.zeros(256, dtype=np.float32),
        ),
        VectorRecord(
            chunk_id="c2", text="hello", role="assistant", session_id="s1", ts="t2",
            vector=np.ones(256, dtype=np.float32),
        ),
    ]
    append_vectors(h, recs)
    loaded = load_all_vectors(h)
    assert [r.chunk_id for r in loaded] == ["c1", "c2"]
    assert loaded[0].vector.shape == (256,)


def test_append_vectors_creates_new_shard_each_call(tmp_home: Path) -> None:
    h = "vec-shards"
    append_vectors(h, [VectorRecord(chunk_id="x", text="x", role="user",
                                    session_id="s", ts="t",
                                    vector=np.zeros(256, dtype=np.float32))])
    append_vectors(h, [VectorRecord(chunk_id="y", text="y", role="user",
                                    session_id="s", ts="t",
                                    vector=np.zeros(256, dtype=np.float32))])
    shards = sorted(vectors_dir(h).glob("*.parquet"))
    assert len(shards) == 2
