from __future__ import annotations

from pathlib import Path

import pytest

from triforge._config import ProjectConfig, save_project_config
from triforge._hashing import project_hash
from triforge.memory.capture import capture_from_payload
from triforge.memory.indexer import run_index_once
from triforge.memory.search import search


def _seed(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    capture_from_payload(
        project,
        {
            "session_id": "s1",
            "transcript": [
                {"role": "user", "content": "How do I add an authentication middleware in Flask?"},
                {"role": "assistant", "content": "Use a before_request handler that checks the JWT cookie."},
                {"role": "user", "content": "What's the difference between a list and a tuple in Python?"},
                {"role": "assistant", "content": "Lists are mutable, tuples are immutable and hashable."},
            ],
        },
    )
    run_index_once(project)
    return project


@pytest.mark.slow
def test_search_returns_relevant_chunk(tmp_home: Path, tmp_path: Path) -> None:
    project = _seed(tmp_path)
    h = project_hash(project)
    results = search(h, "authentication middleware", top_k=2)
    assert len(results) >= 1
    top_text = results[0].text.lower()
    assert any(token in top_text for token in ("auth", "jwt", "before_request"))


def test_search_inactive_project_returns_empty(tmp_home: Path, tmp_path: Path) -> None:
    h = project_hash(tmp_path / "no-such")
    assert search(h, "anything") == []


@pytest.mark.slow
def test_search_modes_run_without_error(tmp_home: Path, tmp_path: Path) -> None:
    project = _seed(tmp_path)
    h = project_hash(project)
    for mode in ("hybrid", "dense", "bm25"):
        results = search(h, "Python tuple", top_k=2, mode=mode)
        assert isinstance(results, list)
