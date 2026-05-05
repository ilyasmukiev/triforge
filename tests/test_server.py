from __future__ import annotations
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from triforge._config import ProjectConfig, save_project_config
from triforge.memory.capture import capture_from_payload
from triforge.memory.indexer import run_index_once
from triforge.memory.server import rag_search_impl


def _seed(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    capture_from_payload(
        project,
        {
            "session_id": "s1",
            "transcript": [
                {"role": "user", "content": "Database migration with alembic"},
                {"role": "assistant", "content": "Use `alembic revision --autogenerate -m 'msg'`"},
            ],
        },
    )
    run_index_once(project)
    return project


@pytest.mark.slow
def test_rag_search_impl_returns_dicts(tmp_home: Path, tmp_path: Path) -> None:
    project = _seed(tmp_path)
    out = rag_search_impl(query="alembic", project_path=str(project), top_k=3)
    assert isinstance(out, list)
    assert out, "expected at least one result"
    first = out[0]
    for key in ("chunk_id", "text", "role", "session_id", "ts", "score", "source"):
        assert key in first


@pytest.mark.slow
def test_rag_search_impl_respects_top_k(tmp_home: Path, tmp_path: Path) -> None:
    project = _seed(tmp_path)
    out = rag_search_impl(query="alembic", project_path=str(project), top_k=1)
    assert len(out) <= 1


def test_server_module_imports_cleanly() -> None:
    importlib.import_module("triforge.memory.server")


def test_triforge_memory_entry_callable() -> None:
    r = subprocess.run(
        [sys.executable, "-c", "from triforge.memory.server import main; print('ok')"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 0
    assert "ok" in r.stdout
