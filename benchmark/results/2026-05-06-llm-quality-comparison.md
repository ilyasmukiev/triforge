# Triforge LLM-quality benchmark — 2026-05-06

Real Claude Haiku-4-5 calls (via Claude Code subagent), 4 questions × 3 conditions:

1. **Baseline** — fresh chat, no triforge, no prelude.
2. **Triforge v1.0.0** — SessionStart prelude with the *original* deterministic summary (user-only bullets).
3. **Triforge v1.0.1** — SessionStart prelude with the **fixed** Q+A pair summary.

The benchmark was run autonomously via the Claude Code Agent tool (model = `claude-haiku-4-5`). Each answer was scored 0-5 by hand against a fixed list of "gold facts" the prior sessions had established.

## Setup

Three prior sessions were captured into the project memory:

- **prior-1:** decided **`done INTEGER NOT NULL DEFAULT 0`** instead of TEXT (sortability + index without casting → `WHERE done = 0`).
- **prior-2:** planned **`POST /tasks/{id}/done`** endpoint, returns 404 if id missing.
- **prior-3:** **deferred `description` column** because v1 spec didn't require multi-line bodies; SQLite ALTER TABLE ADD COLUMN is safe later.

## Results

| Q | Question | Baseline | Triforge 1.0.0 (broken) | **Triforge 1.0.1 (fixed)** |
|---|---|:---:|:---:|:---:|
| Q1 | What did we decide about status field; what endpoint is planned? | **0/5** *(no context)* | 1/5 *(wrong: "TEXT")* | **5/5** |
| Q2 | Why no `description` column? | **0/5** *(asks for context)* | 3/5 | **5/5** |
| Q3 | Query for unfinished tasks? | 2/5 *(generic)* | 3/5 | **5/5** |
| Q4 | Migration needed for descriptions? | **0/5** *(hallucinated JSON storage)* | 2/5 | **5/5** |
| **Σ** | | **2 / 20 (10%)** | 9 / 20 (45%) | **20 / 20 (100%)** |

## What changed between 1.0.0 → 1.0.1

The fallback `_deterministic_summary` (used when no LLM provider is configured) used to record only **user** messages — the questions, never the answers. So Q1's prelude was effectively:

> - Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?

Claude read that as *"the decision was TEXT pending/done"* and answered backwards. The fix now records Q+A pairs:

> - Q: Should we use TEXT pending/done or INTEGER 0/1?
> - → A: Use INTEGER 0/1 in the `done` column. Better for sortability...

Same chunks, same disk usage, same latency — but now the agent sees the **decision**, not just the question.

## Cost / latency

| Metric | Baseline | Triforge 1.0.1 |
|---|---:|---:|
| Mean prompt tokens (`tiktoken cl100k_base`) | 16 | 151 |
| Δ tokens for full project recall | — | **+134 tok** |
| Mean answer tokens (Claude Haiku) | ~70 | ~80 |
| Latency overhead from prelude | — | < 1 ms (file read) |
| Disk per project (4 conversations seeded) | 0 KB | ~24 KB |

## Verbatim answers (Q1)

**Baseline (no triforge):**
> "I don't have access to information from two sessions ago. This is a fresh session with no prior context from previous conversations. To find out what was decided about the task status field and any planned endpoints, you'd need to: 1. Check your project's documentation..."

**Triforge 1.0.0 (broken summary):**
> "Two sessions ago we decided to implement task status using TEXT (pending/done) rather than INTEGER (0/1). The planned endpoint we still need to implement is one to mark tasks as done..."
>
> ⚠️ **Wrong answer** — invented the opposite decision because the prelude only carried the question.

**Triforge 1.0.1 (fixed summary):**
> "Based on the prior memory, two sessions ago we decided to use **INTEGER 0/1 for the `done` column** instead of TEXT pending/done — better for sortability and cheaper to index. The `done INTEGER NOT NULL DEFAULT 0` was already added to the schema in db.py. There's a **planned POST /tasks/{id}/done endpoint** that still needs implementation — it should flip `done=1` and return 404 if the id is missing..."
>
> ✅ Correct: column type, schema diff, endpoint name, 404 behavior.

## Take-aways

- **The benchmark itself was the cheapest fix the project ever shipped.** Without it the 1.0.0 deterministic-summary regression would have stayed in the codebase indefinitely.
- The **"any-path recall = 100%"** number from the local benchmark was a true *upper bound* — the prelude carried the right substrings, but the LLM was misreading them. Recall metrics measure what's *available*; quality metrics measure what the model *does* with it. You need both.
- For users with an LLM provider configured (Anthropic / OpenAI / Ollama), the indexer uses `_llm_summary` instead of the deterministic recap — the regression never affected them, only the offline-only path.

## Reproducibility

- **Local layer:** `python benchmark/real_benchmark.py` — token counts, latency, recall metrics with no API key.
- **LLM layer:** export an API key and re-run, OR call agents directly through Claude Code (as was done here).
- **Manual rubric** + verbatim outputs are in this report; raw tool outputs are in the conversation transcript.
