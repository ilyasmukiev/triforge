# triforge

> **One install — three dimensions of intelligence for Claude Code in any project.**

`triforge` bundles three excellent open-source projects into a single, coherent system that every new Claude Code session in a project can use:

| Layer | Project | Purpose |
|---|---|---|
| 🧠 **Conversation memory** | HippoRAG-2-style graph memory (in-house, inspired by [OSU NLP Group](https://github.com/OSU-NLP-Group/HippoRAG)) | Per-project memory with multi-hop retrieval. New chats start with an automatic prelude and can search past conversations via `rag_search`. |
| 🔍 **Code understanding** | [semble](https://github.com/MinishLab/semble) | Hybrid (BM25 + semantic) code search across 19 languages. |
| 🗄 **Backend for projects** | [InsForge](https://github.com/InsForge/InsForge) | PostgreSQL + pgvector + S3 + Deno functions, exposed via MCP. |

## Why?

Claude Code today suffers from three limitations:

1. **No memory.** Every new chat starts from a blank slate.
2. **Expensive code search.** `grep + cat` burns 100 k+ tokens where smart semantic search would use 2 k.
3. **No light backend layer.** When the agent needs a DB, file storage or functions, that's always manual setup.

`triforge` fixes all three with **one install**, integrating three mature open-source projects into a coherent system. Each layer is an independent MCP server: you can disable or upgrade them separately.

## 60-second start

```bash
pipx install triforge
triforge install
```

That's it. Three MCP servers are now available in every Claude Code session.

To activate **per-project memory**, open Claude Code in your project and run:

```text
> /rag
```

The skill writes hooks into `.claude/settings.local.json`, drops a marker file `.triforge/config.json`, and appends a short section to your `AGENTS.md`. Every subsequent chat in this folder is captured, indexed, and made available to future sessions.

## How memory works (one diagram)

```text
  Stop hook  ──→  chats.jsonl  ──→  SessionEnd hook  ──→  background indexer
                                                                  │
                                                ┌─────────────────┼─────────────────┐
                                                ▼                 ▼                 ▼
                                            summary.md       kg.pkl (graph)    vectors/

  SessionStart hook  ──→  prelude (last ~500 words of summary.md) ──→  Claude's context

  MCP tool `rag_search(query)` ──→ RRF fusion of (PPR over graph) + (cosine) + (BM25)
```

**Privacy by design:** every chunk is filtered by a regex first-pass; if heuristic triggers fire (`secret`, `token`, `password`, `auth`...), an isolated LLM-cleaner subagent is invoked. Data lives in `~/.claude/triforge/{project-hash}/`, never in the project tree.

**Auto-fallback LLM:** the indexer tries `ANTHROPIC_API_KEY → OPENAI_API_KEY → Ollama → dense-only`. No keys? It still works — just without the graph reasoning layer.

## Where next

- [Install](install.md) — what `triforge install` does, how to uninstall.
- [Architecture](architecture.md) — the three MCP servers, the per-project pipeline.
- [Privacy](privacy.md) — what is captured, how secrets are stripped.
- [InsForge mode](insforge-mode.md) — `triforge migrate --to=insforge` for pgvector.
- [Troubleshooting](troubleshooting.md) — Cross-platform notes, common errors.
- [Credits](credits.md) — Authors of the three integrated projects.
