from __future__ import annotations

from pathlib import Path

from triforge._hashing import project_hash


def test_hash_is_12_hex_chars() -> None:
    h = project_hash("/tmp/some/project")
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_is_stable() -> None:
    a = project_hash("/tmp/some/project")
    b = project_hash("/tmp/some/project")
    assert a == b


def test_hash_normalizes_trailing_slash(tmp_path: Path) -> None:
    a = project_hash(tmp_path)
    b = project_hash(str(tmp_path) + "/")
    assert a == b


def test_hash_differs_per_path() -> None:
    a = project_hash("/tmp/proj-a")
    b = project_hash("/tmp/proj-b")
    assert a != b


def test_accepts_pathlib_path() -> None:
    str_h = project_hash("/tmp/x")
    path_h = project_hash(Path("/tmp/x"))
    assert str_h == path_h
