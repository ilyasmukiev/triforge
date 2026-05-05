"""Per-project triforge configuration (.triforge/config.json)."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from triforge._locking import read_json_locked, write_json_locked

CONFIG_FILE = ".triforge/config.json"


@dataclass
class ProjectConfig:
    storage: Literal["local", "insforge"] = "local"
    exclude: list[str] = field(default_factory=list)
    enabled: bool = True
    schema_version: int = 1


def _config_path(project_path: Path) -> Path:
    return Path(project_path) / CONFIG_FILE


def load_project_config(project_path: Path) -> ProjectConfig | None:
    raw = read_json_locked(_config_path(project_path), default=None)
    if raw is None:
        return None
    return ProjectConfig(
        storage=raw.get("storage", "local"),
        exclude=raw.get("exclude", []),
        enabled=raw.get("enabled", True),
        schema_version=raw.get("schema_version", 1),
    )


def save_project_config(project_path: Path, cfg: ProjectConfig) -> None:
    write_json_locked(_config_path(project_path), asdict(cfg))


def is_project_activated(project_path: Path) -> bool:
    return _config_path(project_path).exists()
