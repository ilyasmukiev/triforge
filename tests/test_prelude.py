from __future__ import annotations
from pathlib import Path

from triforge._config import ProjectConfig, save_project_config
from triforge._hashing import project_hash
from triforge.memory.prelude import build_prelude_payload
from triforge.memory.store import append_summary


def test_inactive_project_returns_empty_payload(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    payload = build_prelude_payload(project)
    assert payload == {}


def test_active_project_with_summary_returns_context(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    append_summary(project_hash(project), "## Session s1\n- previous decision X")

    payload = build_prelude_payload(project)
    assert "hookSpecificOutput" in payload
    out = payload["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert "previous decision X" in out["additionalContext"]


def test_active_project_no_summary_returns_empty(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    payload = build_prelude_payload(project)
    assert payload == {}
