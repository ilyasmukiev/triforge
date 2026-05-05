from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "triforge.cli", *args],
        capture_output=True,
        text=True,
    )


def test_cli_help_lists_subcommands() -> None:
    r = _run("--help")
    assert r.returncode == 0
    out = r.stdout + r.stderr
    for cmd in (
        "install",
        "uninstall",
        "status",
        "dump",
        "purge",
        "capture",
        "index",
        "prelude",
    ):
        assert cmd in out, f"missing subcommand in --help: {cmd}\n{out}"


def test_cli_version_works() -> None:
    r = _run("--version")
    assert r.returncode == 0
    assert "triforge" in (r.stdout + r.stderr).lower()


def test_status_for_inactive_project(tmp_home: Path, tmp_path: Path) -> None:
    r = _run("status", "--project", str(tmp_path))
    assert r.returncode == 0
    assert "not activated" in (r.stdout + r.stderr).lower()


def test_dump_shows_summary(tmp_home: Path, tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    from triforge._config import ProjectConfig, save_project_config
    from triforge._hashing import project_hash
    from triforge.memory.store import append_summary

    save_project_config(project, ProjectConfig())
    append_summary(project_hash(project), "## Session ABC\n- decision was X")

    r = _run("dump", "--project", str(project))
    assert r.returncode == 0
    assert "decision was X" in r.stdout


def test_purge_removes_project_dir(tmp_home: Path, tmp_path: Path) -> None:
    from triforge._config import ProjectConfig, save_project_config
    from triforge._hashing import project_hash
    from triforge._paths import project_dir

    project = tmp_path / "p"
    project.mkdir()
    save_project_config(project, ProjectConfig())
    h = project_hash(project)
    project_dir(h)
    r = _run("purge", "--project", str(project), "-y")
    assert r.returncode == 0
    assert not (tmp_home / ".claude" / "triforge" / h).exists()


def test_uninstall_clears_global(tmp_home: Path) -> None:
    from triforge.installer import OUR_SERVER_NAMES, install_global

    install_global()
    r = _run("uninstall")
    assert r.returncode == 0
    data = json.loads((tmp_home / ".claude.json").read_text(encoding="utf-8"))
    for n in OUR_SERVER_NAMES:
        assert n not in data.get("mcpServers", {})
