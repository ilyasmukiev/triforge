"""Global and per-project install actions.

- Global:  patch ``~/.claude.json`` with three MCP servers,
           write ``~/.claude/commands/rag.md``,
           append a section to ``~/.claude/CLAUDE.md``.

- Project: write ``.triforge/config.json``, ``.triforge/.gitignore``,
           ``.claude/settings.local.json`` (with our hooks),
           append ``## Triforge memory`` to ``AGENTS.md`` (or ``CLAUDE.md``).
"""
from __future__ import annotations
import json
import shutil
import sys
from importlib.resources import files as _pkg_files
from pathlib import Path
from typing import Any

from triforge._config import ProjectConfig, save_project_config
from triforge._paths import claude_root

OUR_SERVER_NAMES = ("semble", "insforge", "triforge-memory")

GLOBAL_CLAUDE_MD_SECTION = """
## Triforge MCPs (auto-loaded by `triforge install`)

Three MCP servers are registered globally:
- `semble` — code search across the current project (BM25 + semantic).
- `insforge` — backend-as-a-service (DB / storage / functions).
- `triforge-memory` — per-project chat memory; activated via `/rag` per project.

Use `/rag` inside a project to enable per-project memory there.
"""

PROJECT_AGENTS_SECTION_HEADER = "## Triforge memory"


# ---------------------------------------------------------------------------
# Resource helpers
# ---------------------------------------------------------------------------


def _resource(*parts: str) -> Path:
    base = _pkg_files("triforge")
    p = base
    for part in parts:
        p = p / part
    return Path(str(p))


def _claude_json_path() -> Path:
    """``~/.claude.json`` (Claude Code's user config; sibling of ``~/.claude/``)."""
    return claude_root().parent / ".claude.json"


def _slash_command_path() -> Path:
    return claude_root() / "commands" / "rag.md"


def _global_claude_md_path() -> Path:
    return claude_root() / "CLAUDE.md"


def _triforge_memory_command() -> dict[str, Any]:
    bin_path = shutil.which("triforge-memory")
    if bin_path:
        return {"command": bin_path, "args": []}
    return {"command": sys.executable, "args": ["-m", "triforge.memory.server"]}


def _server_definitions() -> dict[str, dict[str, Any]]:
    return {
        "semble": {"command": "uvx", "args": ["--from", "semble[mcp]", "semble"]},
        "insforge": {"type": "http", "url": "https://mcp.insforge.dev/mcp"},
        "triforge-memory": _triforge_memory_command(),
    }


def _triforge_invocation() -> str:
    """Single shell-friendly command prefix to invoke triforge.

    Prefers the installed console script (single absolute path, no spaces in
    its tail); falls back to ``python -m triforge.cli``.
    """
    bin_ = shutil.which("triforge")
    if bin_:
        return bin_
    return f"{sys.executable} -m triforge.cli"


def _hooks_block() -> dict[str, Any]:
    """Build the hooks JSON programmatically (avoids template-escape bugs)."""
    pre = _triforge_invocation()
    return {
        "SessionStart": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{pre} prelude --project=${{CLAUDE_PROJECT_DIR}}",
                    }
                ],
            }
        ],
        "Stop": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{pre} capture --project=${{CLAUDE_PROJECT_DIR}}",
                    }
                ],
            }
        ],
        "SessionEnd": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{pre} index --project=${{CLAUDE_PROJECT_DIR}} --background",
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Global ~/.claude.json
# ---------------------------------------------------------------------------


def _read_claude_json() -> dict[str, Any]:
    p = _claude_json_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8") or "{}")


def _write_claude_json(data: dict[str, Any]) -> None:
    p = _claude_json_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_mcp_servers() -> list[str]:
    """Idempotently register our three MCP servers in ``~/.claude.json``.

    Preserves any existing servers; returns the list of servers added or
    updated this call.
    """
    data = _read_claude_json()
    servers = data.setdefault("mcpServers", {})
    added: list[str] = []
    for name, spec in _server_definitions().items():
        if servers.get(name) != spec:
            servers[name] = spec
            added.append(name)
    _write_claude_json(data)
    return added


def remove_mcp_servers() -> list[str]:
    """Remove only our servers; leave the user's others untouched."""
    data = _read_claude_json()
    servers = data.get("mcpServers", {})
    removed: list[str] = []
    for name in OUR_SERVER_NAMES:
        if name in servers:
            del servers[name]
            removed.append(name)
    if servers:
        data["mcpServers"] = servers
    elif "mcpServers" in data:
        del data["mcpServers"]
    _write_claude_json(data)
    return removed


# ---------------------------------------------------------------------------
# Global slash-command + CLAUDE.md
# ---------------------------------------------------------------------------


def write_global_slash_command() -> Path:
    src = _resource("skills", "rag.md")
    dst = _slash_command_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def append_global_claude_md() -> None:
    p = _global_claude_md_path()
    body = p.read_text(encoding="utf-8") if p.exists() else ""
    if "Triforge MCPs (auto-loaded" in body:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body + GLOBAL_CLAUDE_MD_SECTION, encoding="utf-8")


def install_global() -> None:
    add_mcp_servers()
    write_global_slash_command()
    append_global_claude_md()


# ---------------------------------------------------------------------------
# Per-project install (the body of `/rag`)
# ---------------------------------------------------------------------------


def install_project_here(project: Path) -> None:
    project = Path(project).resolve()

    # 1. config.json
    if not (project / ".triforge" / "config.json").exists():
        save_project_config(project, ProjectConfig())

    # 2. .triforge/.gitignore
    gitignore = project / ".triforge" / ".gitignore"
    gitignore.write_text("# triforge runtime — do not commit\n*\n", encoding="utf-8")

    # 3. .claude/settings.local.json with hooks (idempotent merge)
    settings_path = project / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    new_hooks = _hooks_block()
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            existing = {}
        merged_hooks = {**existing.get("hooks", {}), **new_hooks}
        existing["hooks"] = merged_hooks
        settings_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        settings_path.write_text(
            json.dumps({"hooks": new_hooks}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # 4. AGENTS.md (or CLAUDE.md fallback)
    section = _resource("templates", "AGENTS_section.md").read_text(encoding="utf-8")
    target = project / "AGENTS.md"
    if not target.exists() and (project / "CLAUDE.md").exists():
        target = project / "CLAUDE.md"
    if not target.exists():
        target.write_text("# Project AGENTS\n", encoding="utf-8")
    body_md = target.read_text(encoding="utf-8")
    if PROJECT_AGENTS_SECTION_HEADER not in body_md:
        target.write_text(body_md.rstrip() + "\n" + section + "\n", encoding="utf-8")


def project_files_present(project: Path) -> bool:
    return (
        (project / ".triforge" / "config.json").exists()
        and (project / ".claude" / "settings.local.json").exists()
    )
