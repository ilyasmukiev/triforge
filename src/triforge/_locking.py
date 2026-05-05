"""Cross-platform advisory file locks for concurrent JSONL/JSON I/O."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import portalocker


def append_locked(path: Path, text: str) -> None:
    """Atomic append-with-lock; creates parent dirs and file if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with portalocker.Lock(str(path), mode="a", flags=portalocker.LOCK_EX) as f:
        f.write(text)


def read_text_locked(path: Path) -> str:
    if not path.exists():
        return ""
    with portalocker.Lock(str(path), mode="r", flags=portalocker.LOCK_SH) as f:
        return f.read()


def write_json_locked(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with portalocker.Lock(str(path), mode="w", flags=portalocker.LOCK_EX) as f:
        f.write(payload)


def read_json_locked(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with portalocker.Lock(str(path), mode="r", flags=portalocker.LOCK_SH) as f:
        return json.loads(f.read())
