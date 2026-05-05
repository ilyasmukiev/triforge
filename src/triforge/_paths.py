"""Cross-platform paths for triforge runtime data.

All per-project memory lives under ``~/.claude/triforge/<hash>/`` so it
sits next to Claude Code's own user data (HOME on Unix, USERPROFILE on
Windows).
"""
from __future__ import annotations
from pathlib import Path


def claude_root() -> Path:
    """``~/.claude/`` — Claude Code's user-data root."""
    return Path.home() / ".claude"


def triforge_root() -> Path:
    """``~/.claude/triforge/`` (created on demand)."""
    p = claude_root() / "triforge"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_dir(project_hash: str) -> Path:
    """``~/.claude/triforge/<hash>/`` (created on demand)."""
    p = triforge_root() / project_hash
    p.mkdir(parents=True, exist_ok=True)
    return p


def chats_jsonl(project_hash: str) -> Path:
    return project_dir(project_hash) / "chats.jsonl"


def state_json(project_hash: str) -> Path:
    return project_dir(project_hash) / "state.json"


def vectors_dir(project_hash: str) -> Path:
    p = project_dir(project_hash) / "vectors"
    p.mkdir(parents=True, exist_ok=True)
    return p


def summary_md(project_hash: str) -> Path:
    return project_dir(project_hash) / "summary.md"
