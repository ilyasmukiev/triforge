from __future__ import annotations
from pathlib import Path

from triforge._locking import (
    append_locked,
    read_json_locked,
    read_text_locked,
    write_json_locked,
)


def test_append_locked_appends_lines(tmp_path: Path) -> None:
    f = tmp_path / "log.jsonl"
    append_locked(f, "first\n")
    append_locked(f, "second\n")
    assert read_text_locked(f) == "first\nsecond\n"


def test_write_then_read_json(tmp_path: Path) -> None:
    f = tmp_path / "state.json"
    write_json_locked(f, {"k": 1})
    assert read_json_locked(f) == {"k": 1}


def test_read_json_missing_returns_default(tmp_path: Path) -> None:
    f = tmp_path / "absent.json"
    assert read_json_locked(f, default={"empty": True}) == {"empty": True}


def test_read_text_missing_returns_empty(tmp_path: Path) -> None:
    f = tmp_path / "absent.txt"
    assert read_text_locked(f) == ""
