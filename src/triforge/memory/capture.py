"""Stop-hook: read Claude Code transcript payload and append to chats.jsonl."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triforge._config import is_project_activated, load_project_config
from triforge._hashing import project_hash
from triforge._privacy import redact
from triforge._privacy_llm import clean_if_needed
from triforge.memory.store import ChatRecord, append_chat


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_pairs(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Pull (role, content) pairs from either a `transcript` array or
    Claude Code's native Stop-hook fields.

    Claude Code's Stop hook delivers something like::

        {"session_id": "...", "transcript_path": "...", ...}

    where `transcript_path` is a JSONL of conversation messages. We accept
    either a pre-parsed `transcript` array (used by tests and our own tooling)
    or read the file pointed to by `transcript_path`.
    """
    if isinstance(payload.get("transcript"), list):
        return [
            (e.get("role", ""), e.get("content", ""))
            for e in payload["transcript"]
            if isinstance(e, dict)
        ]
    path = payload.get("transcript_path")
    if not path or not Path(path).exists():
        return []
    out: list[tuple[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Claude Code transcript format: {"type":"user"/"assistant", "message":{"content":[{"type":"text","text":"..."}]}}
        msg = obj.get("message", {})
        msg_type = obj.get("type") or msg.get("role")
        if msg_type not in {"user", "assistant"}:
            continue
        content = msg.get("content")
        if isinstance(content, str):
            out.append((msg_type, content))
        elif isinstance(content, list):
            text = "".join(
                blk.get("text", "")
                for blk in content
                if isinstance(blk, dict) and blk.get("type") == "text"
            )
            if text:
                out.append((msg_type, text))
    return out


def capture_from_payload(project: Path, payload: dict[str, Any]) -> int:
    """Append redacted user/assistant text from a Claude Code Stop payload.

    Returns the number of records appended (0 if project not activated).
    """
    if not is_project_activated(project):
        return 0

    cfg = load_project_config(project)
    extra = cfg.exclude if cfg else None

    session_id = payload.get("session_id", "unknown")
    pairs = _extract_pairs(payload)

    h = project_hash(project)
    n = 0
    ts = _now_iso()
    for role, content in pairs:
        if role not in {"user", "assistant"} or not content:
            continue
        # 1. fast regex first-pass (always)
        cleaned = redact(content, extra_patterns=extra)
        # 2. heuristic-triggered LLM cleaner (only if a provider is configured
        #    AND trigger words remain after step 1; degrades silently otherwise)
        cleaned = clean_if_needed(cleaned)
        append_chat(
            h,
            ChatRecord(ts=ts, session_id=session_id, role=role, text=cleaned),
        )
        n += 1
    return n


def capture_from_stdin(project: Path) -> int:
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    return capture_from_payload(project, payload)
