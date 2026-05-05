from __future__ import annotations

import json
from pathlib import Path

from triforge.installer import (
    OUR_SERVER_NAMES,
    add_mcp_servers,
    install_global,
    install_project_here,
    project_files_present,
    remove_mcp_servers,
)


def _claude_json(tmp_home: Path) -> Path:
    return tmp_home / ".claude.json"


def test_add_to_empty_creates_file(tmp_home: Path) -> None:
    add_mcp_servers()
    data = json.loads(_claude_json(tmp_home).read_text(encoding="utf-8"))
    for name in OUR_SERVER_NAMES:
        assert name in data["mcpServers"]


def test_add_preserves_existing_servers(tmp_home: Path) -> None:
    _claude_json(tmp_home).write_text(
        json.dumps({"mcpServers": {"user-mcp": {"command": "foo"}}}),
        encoding="utf-8",
    )
    add_mcp_servers()
    data = json.loads(_claude_json(tmp_home).read_text(encoding="utf-8"))
    assert "user-mcp" in data["mcpServers"]
    for name in OUR_SERVER_NAMES:
        assert name in data["mcpServers"]


def test_add_is_idempotent(tmp_home: Path) -> None:
    add_mcp_servers()
    add_mcp_servers()
    data = json.loads(_claude_json(tmp_home).read_text(encoding="utf-8"))
    for name in OUR_SERVER_NAMES:
        assert isinstance(data["mcpServers"][name], dict)


def test_remove_only_removes_ours(tmp_home: Path) -> None:
    _claude_json(tmp_home).write_text(
        json.dumps({"mcpServers": {"user-mcp": {"command": "foo"}}}),
        encoding="utf-8",
    )
    add_mcp_servers()
    remove_mcp_servers()
    data = json.loads(_claude_json(tmp_home).read_text(encoding="utf-8"))
    assert "user-mcp" in data["mcpServers"]
    for name in OUR_SERVER_NAMES:
        assert name not in data.get("mcpServers", {})


def test_install_global_writes_command_file(tmp_home: Path) -> None:
    install_global()
    cmd_file = tmp_home / ".claude" / "commands" / "rag.md"
    assert cmd_file.exists()
    body = cmd_file.read_text(encoding="utf-8")
    assert "/rag" in body or "Activate triforge" in body


def test_install_project_here_creates_marker_and_hooks(
    tmp_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    install_project_here(project)
    assert project_files_present(project)
    assert (project / ".triforge" / "config.json").exists()
    settings = project / ".claude" / "settings.local.json"
    assert settings.exists()
    body = settings.read_text(encoding="utf-8")
    for cmd in ("prelude", "capture", "index"):
        assert cmd in body


def test_install_project_appends_to_agents_md(
    tmp_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    install_project_here(project)
    agents = project / "AGENTS.md"
    assert agents.exists()
    assert "Triforge memory" in agents.read_text(encoding="utf-8")


def test_install_project_does_not_duplicate_section(
    tmp_home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    install_project_here(project)
    install_project_here(project)
    agents = project / "AGENTS.md"
    body = agents.read_text(encoding="utf-8")
    assert body.count("## Triforge memory") == 1
