# triforge

> One install — three dimensions of intelligence for Claude Code in any project.

`triforge` bundles three excellent open-source projects into a single, coherent system that every new Claude Code session in a project can use:

| Layer | Project | Purpose |
|---|---|---|
| 🧠 **Conversation memory** | HippoRAG-2-style graph memory (in-house, inspired by [OSU NLP Group](https://github.com/OSU-NLP-Group/HippoRAG)) | Per-project memory with multi-hop retrieval. New chats start with an automatic prelude and can search past conversations via `rag_search`. |
| 🔍 **Code understanding** | [semble](https://github.com/MinishLab/semble) | Hybrid (BM25 + semantic) code search across 19 languages. |
| 🗄 **Backend for projects** | [InsForge](https://github.com/InsForge/InsForge) | PostgreSQL + pgvector + S3 + Deno functions, exposed via MCP. |

**Status:** `v1.0.1` — published, benchmarked, docs at <https://ilyasmukiev.github.io/triforge/>.

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

## Benchmarks

> All numbers below come from real `claude-haiku-4-5` calls (the cheapest current Anthropic model), running against the Flask + SQLite TODO sandbox at [`benchmark/sandbox-todo-app/`](./benchmark/sandbox-todo-app/). Both scenarios were given identical access to `Read`/`Bash`/`Grep` tools — the only difference is whether the SessionStart prelude was injected.

### Per-question (one user turn that asks about a prior decision)

| Metric | Baseline (no triforge) | Triforge | Δ |
|---|---:|---:|---:|
| **Total tokens** (prompt + tool calls + response) | **45 049** | **36 380** | **−8 669 (−19 %)** |
| Tool calls | 10 | 0 | −10 |
| Wall-clock latency | 66.6 s | 2.9 s | **−63.7 s (23× faster)** |
| Found a correct answer? | ❌ no — gave up | ✅ yes — concrete | — |
| Quality on 4-question rubric (`v1.0.1`) | 2 / 20 (10 %) | **20 / 20 (100 %)** | **10× quality** |

The baseline doesn't *know* the prior decisions, so the agent goes hunting in the filesystem — `ls`, multiple `Read`s, `Grep`s, `git log`, looking for `.omc/` and `.claude/` notes. Ten round-trips later it still can't reconstruct what was decided in a prior chat (the answer was never in code), and it gives up. Triforge front-loads the answer in 134 prelude tokens; the agent replies in one turn with no tools.

### How it scales

Each "memory-recall" question saves about **8 700 tokens** and **64 seconds**. The savings are linear in the number of such questions per session — they multiply, not exponentiate, but for a long iterative session they add up fast:

| Session shape | Memory-recall questions | Token saving | Time saving |
|---|---:|---:|---:|
| Short fix (5 turns, 1 recall) | 1 | ~9 k | ~1 min |
| Typical feature work (20 turns, 5 recalls) | 5 | ~43 k | ~5 min |
| Long iteration (50 turns, 15 recalls) | 15 | **~130 k** | **~16 min** |
| Multi-day project (200 turns, 50 recalls) | 50 | **~430 k** | **~53 min** |

If you only ever do single one-shot tasks where nothing was discussed before, triforge costs you a flat **+134 tokens** per session and gives nothing back — the prelude is pure overhead. **In every other case (which is the common case for project work), the prelude pays for itself many times over.**

### What we're not measuring

- Quality of `rag_search` on adversarial queries (search recall@5 on the seed was 50 % — for the full 100 % story we rely on the prelude *and* search together).
- Cost of running larger Anthropic / OpenAI models (Haiku is the cheapest; with Sonnet or Opus, the absolute dollar savings are 4–10× larger because each saved token is worth more).
- Cost of the indexer's LLM summary calls (one cheap LLM call per session-end; amortised over the whole session).

### Where it can flip the wrong way

A single failure mode worth knowing: if the user asks something that was **never discussed before**, the prelude is 134 tokens of overhead with zero recall to show for it. We measured that case too — net effect is the 134-token tax, no tool overhead saved (because the agent wouldn't have searched the filesystem either, the question wasn't about prior context).

### Reproduce

```bash
git clone https://github.com/ilyasmukiev/triforge && cd triforge
pip install -e ".[dev]"
pip install tiktoken
python benchmark/real_benchmark.py
```

Full benchmark reports:
- [`benchmark/results/2026-05-06-real-benchmark.md`](./benchmark/results/2026-05-06-real-benchmark.md) — local layer (recall, latency, disk)
- [`benchmark/results/2026-05-06-llm-quality-comparison.md`](./benchmark/results/2026-05-06-llm-quality-comparison.md) — quality 10 % → 100 %, with the regression that v1.0.1 fixed
- [`benchmark/results/2026-05-06-realistic-token-comparison.md`](./benchmark/results/2026-05-06-realistic-token-comparison.md) — the realistic with-tools comparison the table above is built from

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

Full docs site: <https://ilyasmukiev.github.io/triforge/>

- [Architecture](./docs/architecture.md)
- [Installation](./docs/install.md)
- [Privacy](./docs/privacy.md)
- [InsForge mode (`triforge migrate --to=insforge`)](./docs/insforge-mode.md)
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

triforge does **not** depend on the upstream `hipporag` package (heavy ML deps, currently incompatible with Python 3.13+); we ship our own lightweight HippoRAG-style implementation in [`memory/openie.py`](./src/triforge/memory/openie.py) and [`memory/graph.py`](./src/triforge/memory/graph.py) — same idea, pure-Python PPR fallback, no scipy required.

### Inspiration

The decision to use a HippoRAG-style approach for chat memory was inspired by the article «Ваш RAG не умеет думать. А мой умеет» by **rRenegat**, published 2026-04-24 on Habr (RUVDS): <https://habr.com/ru/companies/ruvds/articles/1025812/>.

---

## License

[Apache License 2.0](./LICENSE). See [`NOTICE`](./NOTICE) for full third-party attribution.
