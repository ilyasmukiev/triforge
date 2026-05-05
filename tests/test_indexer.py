from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from triforge._config import ProjectConfig, save_project_config
from triforge._hashing import project_hash
from triforge.memory.capture import capture_from_payload
from triforge.memory.indexer import run_index_once
from triforge.memory.store import (
    iter_unindexed_chats,
    load_all_vectors,
    read_summary_tail,
)


def _activate_with_chats(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    capture_from_payload(
        project,
        {
            "session_id": "s1",
            "transcript": [
                {"role": "user", "content": "Let's add an /done endpoint"},
                {"role": "assistant", "content": "Done, edited app.py:42"},
            ],
        },
    )
    return project


@pytest.mark.slow
def test_indexer_is_idempotent(tmp_home: Path, tmp_path: Path) -> None:
    project = _activate_with_chats(tmp_path)
    h = project_hash(project)
    n1 = run_index_once(project)
    assert n1 == 2
    assert len(load_all_vectors(h)) == 2

    n2 = run_index_once(project)
    assert n2 == 0
    assert len(load_all_vectors(h)) == 2


@pytest.mark.slow
def test_indexer_advances_state(tmp_home: Path, tmp_path: Path) -> None:
    project = _activate_with_chats(tmp_path)
    run_index_once(project)
    h = project_hash(project)
    assert list(iter_unindexed_chats(h)) == []


@pytest.mark.slow
def test_indexer_writes_summary(tmp_home: Path, tmp_path: Path) -> None:
    project = _activate_with_chats(tmp_path)
    run_index_once(project)
    body = read_summary_tail(project_hash(project))
    assert "s1" in body
    assert len(body) > 0


@pytest.mark.slow
def test_background_indexer_returns_quickly(tmp_home: Path, tmp_path: Path) -> None:
    project = _activate_with_chats(tmp_path)
    t0 = time.time()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "triforge.cli",
            "index",
            "--project",
            str(project),
            "--background",
        ],
        check=True,
        timeout=10,
    )
    elapsed = time.time() - t0
    assert elapsed < 5
