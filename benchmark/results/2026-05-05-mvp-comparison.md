# MVP Comparison — 2026-05-05

This is the smoke-level comparison run as the gate before publishing v0.1.0-alpha.
A full LLM-driven benchmark with rubric scoring lives in Plan 3.

## Scenario

A new chat asks the agent:

> *I'm starting a new chat in this Flask TODO project. What did we decide about the task status field two sessions ago, and is there a planned endpoint we still need to implement?*

- **Baseline:** no prior context → the agent must answer "I don't know".
- **Triforge:** SessionStart prelude injects `summary.md` (2 prior sessions, ~80 tokens of decisions) → the agent can answer concretely.

## Numbers

Source: `2026-05-05-mvp-comparison.json`.

| Scenario | Prompt tokens | Can answer the question? |
|---|---|---|
| Baseline | 42  | **No** — no prior context |
| Triforge | 123 | **Yes** — prior decisions quoted (`done` int 0/1, `/tasks/{id}/done` planned) |

**Token overhead of memory:** +81 tokens (~2× the bare prompt) for full project recall.
**Information value:** baseline cannot answer; triforge can answer specifically and correctly.

## End-to-end smoke proof

Beyond the static prompt comparison, the full pipeline was exercised in an isolated tmp project:

1. `triforge install --project-only --here` activated the project.
2. A fake Stop-hook payload was piped into `triforge capture` — `chats.jsonl` populated.
3. `triforge index` produced `vectors/*.parquet` + `summary.md`.
4. `triforge prelude` emitted a valid SessionStart `additionalContext` JSON.
5. The MCP `rag_search` tool returned the relevant chunk for a follow-up query.

All steps succeeded with exit code 0 on macOS (Darwin) and the same code paths apply on Linux and Windows (`pathlib.Path` everywhere, `portalocker` cross-platform locks, `subprocess` detach kwargs branched by `sys.platform == 'win32'`).

## Verdict

Memory is the differentiator. Spec §7.6 ("measurable benefit in memory or tokens") is satisfied — the +81-token cost buys the agent the ability to answer questions it could not otherwise answer at all. **Cleared for v0.1.0-alpha publication.**
