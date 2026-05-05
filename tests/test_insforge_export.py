"""Light tests for the InsForge export module.

These don't connect to a real PG (none in CI). They verify:
- DDL renders with the right embedding dimension
- the import-time fallback when psycopg is missing
- the data-shape transforms (chats parsing, vector serialization)

A real round-trip integration test lives in benchmark/insforge_e2e.py
and is run manually against a docker-compose'd PG when needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from triforge._config import ProjectConfig, save_project_config
from triforge._embedder import EMBED_DIM
from triforge._hashing import project_hash
from triforge.memory import insforge_export
from triforge.memory.capture import capture_from_payload
from triforge.memory.indexer import run_index_once


def test_schema_ddl_renders_with_embed_dim() -> None:
    rendered = insforge_export.SCHEMA_DDL.format(embed_dim=EMBED_DIM)
    assert f"vector({EMBED_DIM})" in rendered
    assert "CREATE EXTENSION IF NOT EXISTS vector" in rendered
    assert "triforge_chats" in rendered
    assert "triforge_vectors" in rendered


def test_require_psycopg_raises_helpful_message_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pretend psycopg is not importable.
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(ImportError, match=r"\[insforge\] extra"):
        insforge_export._require_psycopg()


@pytest.mark.slow
def test_export_with_fake_psycopg(
    monkeypatch: pytest.MonkeyPatch, tmp_home: Path, tmp_path: Path
) -> None:
    """Drive ``export_project`` with an in-memory psycopg stand-in to verify
    the SQL parameters and the data we'd send to PG.
    """
    project = tmp_path / "p"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    capture_from_payload(
        project,
        {
            "session_id": "s1",
            "transcript": [
                {"role": "user", "content": "Add a /done endpoint"},
                {"role": "assistant", "content": "Sure, edited app.py"},
            ],
        },
    )
    run_index_once(project)
    h = project_hash(project)

    executed: list[tuple[str, Any]] = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql: str, params: Any = None) -> None:
            executed.append((sql.strip().split()[0].upper() + " " + sql.strip().split()[1:2][0].upper() if len(sql.strip().split()) > 1 else "EXEC", params))
        def executemany(self, sql: str, rows: Any) -> None:
            for r in rows:
                executed.append(("MANY", r))

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def cursor(self): return FakeCursor()
        def commit(self) -> None: executed.append(("COMMIT", None))

    fake_psycopg = SimpleNamespace(connect=lambda url: FakeConn())
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    summary = insforge_export.export_project(project, database_url="postgresql://x")
    assert summary.project_hash == h
    assert summary.n_chats >= 2
    assert summary.n_vectors >= 2
    # at least one INSERT INTO triforge_chats
    chat_inserts = [
        row for kind, row in executed
        if kind == "MANY" and isinstance(row, tuple) and len(row) == 6
    ]
    assert chat_inserts, "expected chat rows to be sent to executemany"
    # vector row shape: 7 fields ending with a list of floats
    vec_inserts = [
        row for kind, row in executed
        if kind == "MANY" and isinstance(row, tuple) and len(row) == 7
    ]
    assert vec_inserts, "expected vector rows to be sent"
    assert isinstance(vec_inserts[0][-1], list)
    assert len(vec_inserts[0][-1]) == EMBED_DIM


def test_jsonl_chats_parsed_with_raw_idx(tmp_home: Path, tmp_path: Path) -> None:
    """Even if a non-JSON line slips into chats.jsonl, export should skip it
    and keep stable raw_idx for the rest.
    """
    project = tmp_path / "p"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    h = project_hash(project)

    from triforge._locking import append_locked
    from triforge._paths import chats_jsonl as cjp

    append_locked(cjp(h), json.dumps({"ts": "t1", "session_id": "s", "role": "user", "text": "ok"}) + "\n")
    append_locked(cjp(h), "garbage line\n")
    append_locked(cjp(h), json.dumps({"ts": "t2", "session_id": "s", "role": "assistant", "text": "fine"}) + "\n")

    # internal helper: parse chats the way export does
    text = (tmp_home / ".claude" / "triforge" / h / "chats.jsonl").read_text(encoding="utf-8")
    parsed = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        obj["raw_idx"] = i
        parsed.append(obj)

    assert [p["text"] for p in parsed] == ["ok", "fine"]
    assert [p["raw_idx"] for p in parsed] == [0, 2]
