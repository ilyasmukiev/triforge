"""Export per-project memory to a PostgreSQL + pgvector store.

Designed to dump triforge's local memory into the database that ships
with InsForge (`docker compose -f docker-compose.prod.yml up`), or into
any standalone PostgreSQL with the ``pgvector`` extension.

Schema (created on first export, ``CREATE TABLE IF NOT EXISTS``):

    triforge_projects(project_hash text PRIMARY KEY, project_path text, ...)
    triforge_chats(project_hash, ts, session_id, role, text, raw_idx)
    triforge_vectors(project_hash, chunk_id, text, role, session_id, ts, embedding vector(N))
    triforge_summaries(project_hash, ts, body)
    triforge_triplets(project_hash, subject, relation, object, chunks)

This module is import-light — heavy deps (``psycopg``, ``pgvector``)
are loaded lazily so users without the ``[insforge]`` extra still get
a clean import error only when they actually try to migrate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from triforge._embedder import EMBED_DIM
from triforge._hashing import project_hash
from triforge._locking import read_text_locked
from triforge._paths import chats_jsonl, summary_md
from triforge.memory.store import load_all_vectors


@dataclass
class ExportSummary:
    project_hash: str
    n_chats: int
    n_vectors: int
    n_summary_bytes: int


def _require_psycopg():
    try:
        import psycopg
    except ImportError as e:
        raise ImportError(
            "InsForge export requires the [insforge] extra. "
            "Install with: pip install 'triforge[insforge]'"
        ) from e
    return psycopg


SCHEMA_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS triforge_projects (
    project_hash text PRIMARY KEY,
    project_path text,
    last_export_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS triforge_chats (
    project_hash text NOT NULL REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    raw_idx int NOT NULL,
    ts text NOT NULL,
    session_id text NOT NULL,
    role text NOT NULL,
    text text NOT NULL,
    PRIMARY KEY (project_hash, raw_idx)
);

CREATE TABLE IF NOT EXISTS triforge_vectors (
    project_hash text NOT NULL REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    chunk_id text NOT NULL,
    text text NOT NULL,
    role text NOT NULL,
    session_id text NOT NULL,
    ts text NOT NULL,
    embedding vector({embed_dim}) NOT NULL,
    PRIMARY KEY (project_hash, chunk_id)
);
CREATE INDEX IF NOT EXISTS triforge_vectors_embedding_idx
    ON triforge_vectors USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS triforge_summaries (
    project_hash text NOT NULL REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    body text NOT NULL,
    written_at timestamptz NOT NULL DEFAULT now()
);
""".strip()


def ensure_schema(conn: Any) -> None:
    """Create tables + pgvector extension if they do not exist."""
    with conn.cursor() as cur:
        for stmt in SCHEMA_DDL.format(embed_dim=EMBED_DIM).split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
    conn.commit()


def export_project(
    project: Path,
    *,
    database_url: str,
    truncate: bool = False,
) -> ExportSummary:
    """Dump one project's local memory into PG. Idempotent on (project, chunk_id).

    If ``truncate`` is true, all existing rows for this project are removed first.
    """
    psycopg = _require_psycopg()

    project = Path(project).resolve()
    h = project_hash(project)

    # Read local state
    chats_text = read_text_locked(chats_jsonl(h))
    chats: list[dict[str, Any]] = []
    for i, line in enumerate(chats_text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        obj["raw_idx"] = i
        chats.append(obj)

    vectors = load_all_vectors(h)
    summary_text = read_text_locked(summary_md(h))

    with psycopg.connect(database_url) as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO triforge_projects (project_hash, project_path)
                VALUES (%s, %s)
                ON CONFLICT (project_hash) DO UPDATE
                SET project_path = EXCLUDED.project_path,
                    last_export_at = now()
                """,
                (h, str(project)),
            )

            if truncate:
                cur.execute("DELETE FROM triforge_chats WHERE project_hash = %s", (h,))
                cur.execute("DELETE FROM triforge_vectors WHERE project_hash = %s", (h,))
                cur.execute("DELETE FROM triforge_summaries WHERE project_hash = %s", (h,))

            # chats
            cur.executemany(
                """
                INSERT INTO triforge_chats (project_hash, raw_idx, ts, session_id, role, text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_hash, raw_idx) DO UPDATE
                SET ts = EXCLUDED.ts,
                    session_id = EXCLUDED.session_id,
                    role = EXCLUDED.role,
                    text = EXCLUDED.text
                """,
                [
                    (h, c["raw_idx"], c["ts"], c["session_id"], c["role"], c["text"])
                    for c in chats
                ],
            )

            # vectors (pgvector accepts python list/tuple of floats)
            cur.executemany(
                """
                INSERT INTO triforge_vectors
                    (project_hash, chunk_id, text, role, session_id, ts, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_hash, chunk_id) DO UPDATE
                SET text = EXCLUDED.text,
                    role = EXCLUDED.role,
                    session_id = EXCLUDED.session_id,
                    ts = EXCLUDED.ts,
                    embedding = EXCLUDED.embedding
                """,
                [
                    (h, v.chunk_id, v.text, v.role, v.session_id, v.ts, v.vector.tolist())
                    for v in vectors
                ],
            )

            # summary (single row, append-style — store latest snapshot)
            if summary_text.strip():
                cur.execute(
                    "INSERT INTO triforge_summaries (project_hash, body) VALUES (%s, %s)",
                    (h, summary_text),
                )

        conn.commit()

    return ExportSummary(
        project_hash=h,
        n_chats=len(chats),
        n_vectors=len(vectors),
        n_summary_bytes=len(summary_text),
    )
