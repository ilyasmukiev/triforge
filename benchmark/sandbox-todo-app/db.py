"""SQLite layer for the sandbox TODO app."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB = Path(__file__).parent / "todo.sqlite"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def list_tasks() -> list[dict[str, Any]]:
    with _conn() as c:
        return [
            dict(r) for r in c.execute("SELECT id, title, done FROM tasks ORDER BY id")
        ]


def add_task(title: str) -> dict[str, Any]:
    with _conn() as c:
        cur = c.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        return {"id": cur.lastrowid, "title": title, "done": 0}


def get_task(tid: int) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (tid,)
        ).fetchone()
        return dict(row) if row else None


def mark_done(tid: int) -> bool:
    with _conn() as c:
        cur = c.execute("UPDATE tasks SET done = 1 WHERE id = ?", (tid,))
        return cur.rowcount > 0
