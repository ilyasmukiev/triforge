# Architecture

## Three independent MCP servers

`triforge install` adds three entries to `~/.claude.json`. They are independent — disable or upgrade each separately.

```text
                  ┌──────────────────────────────────────────┐
                  │             Claude Code (CLI)             │
                  │  ~/.claude.json (auto-loaded everywhere)  │
                  └────┬──────────────┬───────────────┬──────┘
                       │              │               │
              ┌────────▼──┐  ┌────────▼────┐  ┌──────▼──────────┐
              │  semble   │  │  InsForge   │  │ triforge-memory │
              │  (MCP)    │  │  (MCP)      │  │     (MCP)       │
              │  CODE     │  │  BACKEND    │  │  CHAT MEMORY    │
              └───────────┘  └─────────────┘  └─────────────────┘
```

| Server | What it does | Triggered by |
|---|---|---|
| `semble` | Hybrid (BM25 + semantic) code search across 19 languages. From [MinishLab](https://github.com/MinishLab/semble), MIT. | Agent initiative — only consumes tokens when used. |
| `insforge` | Backend-as-a-service: PostgreSQL + pgvector, S3, Deno functions. From [InsForge AI](https://github.com/InsForge/InsForge), Apache-2.0. | Agent initiative. Cloud `https://mcp.insforge.dev/mcp` by default; replace with self-hosted URL as needed. |
| `triforge-memory` | Per-project chat memory. The `rag_search` tool, the SessionStart prelude. | Auto-loaded. **No-op** until `/rag` is run inside a project. |

## Per-project memory pipeline

```text
        ┌──────────────────────────────────────────────────────────────┐
        │               INSIDE A /rag-ACTIVATED PROJECT                │
        └──────────────────────────────────────────────────────────────┘

  (1) CAPTURE — Stop hook, instant, no LLM
  ───────────────────────────────────────
  user: "fix auth bug"        ─┐
  assistant: "<thinking>...     ─┐
              <Edit tool ...>    │── stripped + redacted → JSONL
              done, line 42"     │
                                 ▼
                  ~/.claude/triforge/{hash}/chats.jsonl

  (2) INDEX — SessionEnd hook, background, idempotent
  ───────────────────────────────────────────────────
                  chats.jsonl  (offset cursor in state.json)
                       │
                       ▼
              ┌─────────────────────────┐
              │  triforge-indexer        │  (a separate detached process;
              │  - dense embeddings      │   does not block UX on session exit)
              │  - LLM summary*          │
              │  - LLM OpenIE → graph*   │  *only if any LLM provider is up
              └────┬───────┬───────┬─────┘
                   │       │       │
                   ▼       ▼       ▼
              vectors/   summary.md   kg.pkl

  (3) RETRIEVE — two paths
  ────────────────────────
   A. SessionStart hook  →  reads summary.md tail (≤ 3500 chars)
                         →  emits hookSpecificOutput.additionalContext
                         →  Claude sees the recap in the first turn

   B. MCP tool `rag_search(query)`
       ↓
       ┌──── dense cosine ────┐
       ├──── BM25 lexical ────┤── Reciprocal Rank Fusion ──→ top-K chunks
       └──── graph PPR* ──────┘   *if kg.pkl was built
```

## Storage layout

For each project, all runtime data lives under `~/.claude/triforge/{sha256(abs_path)[:12]}/`:

```text
chats.jsonl           one JSON-line per (user|assistant) turn
state.json            {"last_indexed_offset": N}
vectors/              parquet shards (one per index pass)
   YYYYMMDDTHHMMSS.parquet
summary.md            append-only LLM-or-deterministic summary
kg.pkl                NetworkX MultiDiGraph (built only if LLM available)
errors.log            indexer failures (rare)
```

## Cross-platform

- **Paths** — `pathlib.Path` everywhere, no hardcoded separators.
- **Locks** — [`portalocker`](https://pypi.org/project/portalocker/) wraps both Unix `flock` and Win32 `LockFileEx`.
- **Background** — `subprocess.Popen` with `start_new_session=True` on Unix, `creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP` on Windows.
- **Hooks** — the absolute path to the `triforge` console script is baked into `.claude/settings.local.json` at activation time, so `${CLAUDE_PROJECT_DIR}` is the only env-var the hook depends on.
- **CI** — matrix of `ubuntu-latest`, `macos-latest`, `windows-latest` × Python 3.10, 3.11, 3.12.

## Embedding model

`minishlab/potion-base-8M` from MinishLab — a static [`model2vec`](https://github.com/MinishLab/model2vec) model:

- ~30 MB on disk
- 256-dim float32 vectors
- CPU-only, no PyTorch
- p50 encode latency ~1 ms per chunk
- Multilingual (works on Russian, English, code identifiers)

Cached under HuggingFace's standard `~/.cache/huggingface/hub/`. First run downloads automatically.
