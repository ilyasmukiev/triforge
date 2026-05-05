# triforge

> One install — three dimensions of intelligence for Claude Code in any project.

`triforge` bundles three excellent open-source projects into a single, coherent system that every new Claude Code session in a project can use:

| Layer | Project | Purpose |
|---|---|---|
| 🧠 **Conversation memory** | [HippoRAG 2](https://github.com/OSU-NLP-Group/HippoRAG) | Per-project graph memory with multi-hop reasoning. New chats start with an automatic prelude and can search past conversations via `rag_search`. |
| 🔍 **Code understanding** | [semble](https://github.com/MinishLab/semble) | Hybrid (BM25 + semantic) code search across 19 languages. Indexing < 1 s, p50 latency 1.5 ms, ~94 % token savings vs. `grep + read`. |
| 🗄 **Backend for projects** | [InsForge](https://github.com/InsForge/InsForge) | PostgreSQL + pgvector + S3 + Deno functions, exposed via MCP. The agent itself can deploy, migrate, set up auth. |

**Status:** alpha (`v0.1.0` work in progress). Spec at [`docs/superpowers/specs/2026-05-05-triforge-design.md`](./docs/superpowers/specs/2026-05-05-triforge-design.md).

---

## Why triforge?

Claude Code today suffers from three limitations:

1. **No memory.** Every new chat starts from a blank slate.
2. **Expensive code search.** `grep + cat` burns 100 k+ tokens where smart semantic search would use 2 k.
3. **No light backend layer.** When the agent needs a DB, file storage or functions, that's always manual setup.

`triforge` fixes all three with **one install**, integrating three mature open-source projects into a coherent system. Each layer is an independent MCP server: you can disable or upgrade them separately.

---

## Quick install

> Requires: Python ≥ 3.10, [`pipx`](https://pipx.pypa.io/), Claude Code CLI.

```bash
pipx install triforge
triforge install
```

That's it. Three MCP servers are now available in every Claude Code session.

To activate **per-project memory**, open Claude Code in your project and run:

```
> /rag
```

The skill writes hooks into `.claude/settings.local.json`, drops a marker file `.triforge/config.json`, and appends a short section to your `AGENTS.md`. Every subsequent chat in this folder is captured, indexed, and made available to future sessions.

---

## How memory works (in one diagram)

```
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

---

## Documentation

Full docs are in [`docs/`](./docs):

- [Architecture](./docs/architecture.md)
- [Installation](./docs/install.md)
- [Privacy](./docs/privacy.md)
- [InsForge mode (`--storage=insforge`)](./docs/insforge-mode.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [Credits](./docs/credits.md)

---

## Acknowledgments

`triforge` stands on the shoulders of three brilliant open-source projects. All credit for the algorithms, models and code of the components belongs to their authors — `triforge` is the integration layer.

### semble — Code search for agents

- **Project:** <https://github.com/MinishLab/semble>
- **Authors:** **Thomas van Dongen** ([@Pringled](https://github.com/Pringled)), **Stéphan Tulkens** ([@stephantul](https://github.com/stephantul))
- **Org:** [MinishLab / minish.ai](https://minish.ai/)
- **License:** MIT

### InsForge — Backend-as-a-Service for AI agents

- **Project:** <https://github.com/InsForge/InsForge>
- **Org:** **InsForge AI, Inc.**
- **License:** Apache-2.0

### HippoRAG 2 — Neurobiologically-inspired GraphRAG

- **Project:** <https://github.com/OSU-NLP-Group/HippoRAG>
- **Papers:** [NeurIPS'24](https://arxiv.org/abs/2405.14831) · [ICML'25](https://arxiv.org/abs/2502.14802)
- **Org:** **OSU NLP Group** — Ohio State University
- **License:** Apache-2.0

### Inspiration

The idea of using HippoRAG 2 for chat memory was inspired by the article «Ваш RAG не умеет думать. А мой умеет» by **rRenegat**, published 2026-04-24 on Habr (RUVDS): <https://habr.com/ru/companies/ruvds/articles/1025812/>.

---

## License

[Apache License 2.0](./LICENSE). See [`NOTICE`](./NOTICE) for full third-party attribution.
