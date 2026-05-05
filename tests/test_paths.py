from __future__ import annotations

from pathlib import Path

from triforge._paths import (
    chats_jsonl,
    claude_root,
    project_dir,
    state_json,
    summary_md,
    triforge_root,
    vectors_dir,
)


def test_claude_root_is_under_home(tmp_home: Path) -> None:
    assert claude_root() == tmp_home / ".claude"


def test_triforge_root_is_under_claude(tmp_home: Path) -> None:
    assert triforge_root() == tmp_home / ".claude" / "triforge"


def test_project_dir_uses_provided_hash(tmp_home: Path) -> None:
    p = project_dir("abc123def456")
    assert p == tmp_home / ".claude" / "triforge" / "abc123def456"
    assert p.exists()


def test_per_project_files(tmp_home: Path) -> None:
    h = "deadbeefcafe"
    assert chats_jsonl(h) == project_dir(h) / "chats.jsonl"
    assert state_json(h) == project_dir(h) / "state.json"
    assert vectors_dir(h) == project_dir(h) / "vectors"
    assert summary_md(h) == project_dir(h) / "summary.md"
