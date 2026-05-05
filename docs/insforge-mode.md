# InsForge mode

By default `triforge` keeps everything in `~/.claude/triforge/<hash>/`: SQLite-free JSONL + parquet shards + a NetworkX pickle. That's perfect for a single user on a single machine.

Sometimes you want **more**: SQL access to your memory, multi-machine sync, central backup, vector indexes you can query from your own apps. That's where the `insforge` target comes in.

## What it does

`triforge migrate --to=insforge` exports a project's memory into a PostgreSQL database with the [pgvector](https://github.com/pgvector/pgvector) extension installed. It's idempotent on `(project_hash, chunk_id)`, so you can re-run safely.

## Schema

Created on first migration via `CREATE TABLE IF NOT EXISTS`:

```sql
CREATE TABLE triforge_projects (
    project_hash text PRIMARY KEY,
    project_path text,
    last_export_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE triforge_chats (
    project_hash text REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    raw_idx int,
    ts text,
    session_id text,
    role text,
    text text,
    PRIMARY KEY (project_hash, raw_idx)
);

CREATE TABLE triforge_vectors (
    project_hash text REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    chunk_id text,
    text text, role text, session_id text, ts text,
    embedding vector(256),
    PRIMARY KEY (project_hash, chunk_id)
);
CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE triforge_summaries (
    project_hash text REFERENCES triforge_projects(project_hash) ON DELETE CASCADE,
    body text,
    written_at timestamptz NOT NULL DEFAULT now()
);
```

## Setup

### Option A — InsForge (recommended)

Spin up [InsForge](https://github.com/InsForge/InsForge) self-hosted (it ships PostgreSQL + pgvector preconfigured):

```bash
git clone https://github.com/InsForge/InsForge.git
cd InsForge
cp .env.example .env
# edit .env (POSTGRES_PASSWORD, JWT_SECRET, ENCRYPTION_KEY, ACCESS_API_KEY, ADMIN_EMAIL, ADMIN_PASSWORD)
docker compose -f docker-compose.prod.yml up -d
```

Then:

```bash
pipx install 'triforge[insforge]'
export DATABASE_URL='postgresql://postgres:<password>@localhost:5432/postgres'
cd your-project
triforge migrate --to=insforge
```

### Option B — your own PostgreSQL

Any PostgreSQL ≥ 12 with pgvector works:

```sql
-- once per database
CREATE EXTENSION IF NOT EXISTS vector;
```

Then:

```bash
pipx install 'triforge[insforge]'
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
cd your-project
triforge migrate --to=insforge
```

## Re-running the migration

Re-running keeps the same data; rows update in place via `ON CONFLICT (...) DO UPDATE`. To wipe a project's slate first:

```bash
triforge migrate --to=insforge --truncate
```

## Querying from your own code

Once exported, your data is just SQL:

```sql
-- recent decisions across all projects
SELECT project_path, body, written_at
FROM triforge_summaries s
JOIN triforge_projects p USING (project_hash)
ORDER BY written_at DESC
LIMIT 20;

-- nearest 10 vectors to a query embedding for a single project
SELECT chunk_id, text, role, session_id,
       1 - (embedding <=> %(qvec)s::vector) AS cosine
FROM triforge_vectors
WHERE project_hash = %(hash)s
ORDER BY embedding <=> %(qvec)s::vector
LIMIT 10;
```

## Limitations / scope

`migrate --to=insforge` is **export-only** in v1.0. The normal capture/index/search runtime still uses the local store. We chose this scope for v1.0 because:

- **Reliability:** local capture cannot fail because of a remote outage.
- **Privacy:** an opt-in export is easier to reason about than a runtime that always talks to the network.
- **Simplicity:** it's one new dep (`psycopg`) and one CLI command.

A read-write `--storage=insforge` runtime backend (where capture/index/search go to PG directly) is on the roadmap; track it under [issues](https://github.com/ilyasmukiev/triforge/issues).
