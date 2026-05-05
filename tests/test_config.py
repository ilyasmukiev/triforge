from __future__ import annotations
from pathlib import Path

from triforge._config import (
    ProjectConfig,
    is_project_activated,
    load_project_config,
    save_project_config,
)


def test_default_config_has_sane_values() -> None:
    cfg = ProjectConfig()
    assert cfg.storage == "local"
    assert cfg.exclude == []
    assert cfg.enabled is True


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    cfg = ProjectConfig(storage="local", exclude=["secret_.*"], enabled=True)
    save_project_config(tmp_path, cfg)
    loaded = load_project_config(tmp_path)
    assert loaded == cfg


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_project_config(tmp_path) is None


def test_is_project_activated(tmp_path: Path) -> None:
    assert not is_project_activated(tmp_path)
    save_project_config(tmp_path, ProjectConfig())
    assert is_project_activated(tmp_path)
