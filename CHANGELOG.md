# Changelog

All notable changes to `triforge` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-alpha] — 2026-05-05

The first end-to-end MVP. Three MCP servers register globally with one `triforge install`; per-project chat memory activates with `/rag` inside any project.

### Added

- **Three MCP servers** registered globally in `~/.claude.json` by `triforge install`:
  - `semble` (MIT, MinishLab) — code search across the current project (BM25 + semantic).
  - `insforge` (Apache-2.0, InsForge AI) — backend-as-a-service (DB / storage / functions / pgvector).
  - `triforge-memory` (Apache-2.0, this project) — per-project chat memory with `rag_search` tool.
- **`/rag` slash-command** — inside a project, the agent runs `triforge install --project-only --here` to write `.triforge/config.json`, `.claude/settings.local.json` (with `SessionStart` / `Stop` / `SessionEnd` hooks), `.triforge/.gitignore`, and append a `## Triforge memory` section to `AGENTS.md` (or `CLAUDE.md`).
- **Capture pipeline** (`Stop` hook): reads Claude Code transcript (array or `transcript_path` JSONL), redacts secrets via regex (`OPENAI_API_KEY=…`, `Bearer …`, JWT, AWS keys, `password=…`, PEM blocks, plus user patterns), appends to `chats.jsonl`. Cross-platform via `portalocker`.
- **Indexer** (`SessionEnd` hook, background-detached): embeds new chats with `model2vec` (`potion-base-8M`, 256-dim, CPU-only), writes parquet shards into `~/.claude/triforge/{project-hash}/vectors/`, appends a session summary into `summary.md`. Idempotent via `state.json` offset; Windows uses `DETACHED_PROCESS` flags, Unix uses `start_new_session=True`.
- **Prelude** (`SessionStart` hook): emits Claude Code `additionalContext` JSON containing the tail of `summary.md` (≤ 3500 chars), so every new chat starts with the project's prior context.
- **`rag_search` MCP tool**: hybrid retrieval (dense cosine + BM25 + Reciprocal Rank Fusion). Modes: `hybrid` (default), `dense`, `bm25`.
- **Management CLI**: `triforge {install,uninstall,status,dump,purge,capture,index,prelude}` (Typer + Rich).
- **Cross-platform**: macOS, Linux, Windows (`pathlib.Path` everywhere; CI matrix tests 3 OS × 3 Python versions).
- **MVP benchmark** (`benchmark/`): sandbox Flask TODO + `compare.py` token-comparison script. Release-gate report in `benchmark/results/2026-05-05-mvp-comparison.md`.
- **Tests**: 53 fast + 11 slow, all passing locally on Darwin 25.2 with Python 3.14.

### Out of scope (deferred)

- HippoRAG 2 graph memory + multi-hop reasoning (Plan 2).
- Auto-fallback LLM chain (`ANTHROPIC → OPENAI → Ollama → dense-only`) (Plan 2).
- Heuristic-triggered LLM-cleaner privacy subagent (Plan 2; MVP uses regex first-pass only).
- InsForge-backed pgvector storage (Plan 3).
- Full 4-task × 2-scenario LLM-driven benchmark with rubric scoring (Plan 3).
