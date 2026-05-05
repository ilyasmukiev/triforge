from __future__ import annotations
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Re-root HOME / USERPROFILE to an isolated tmp dir for filesystem-touching tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path
