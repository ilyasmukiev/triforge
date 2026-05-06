# triforge real benchmark — 2026-05-06

Run: `python benchmark/real_benchmark.py`
Generated: 2026-05-06T00:38:31.612393+00:00
Tokens counted via `tiktoken` `cl100k_base` (close to Claude tokenization).

## Setup

The benchmark seeds 3 prior sessions of conversation about a tiny
Flask + SQLite TODO project (decisions about INTEGER 0/1 status field,
a planned `POST /tasks/{id}/done` endpoint, and the `description`
column being deferred).

Then 4 follow-up questions are evaluated under two scenarios:

- **A. Baseline** — chat starts cold; only the question is sent.
- **B. Triforge** — `SessionStart` prelude injects ~140 tokens of
  prior-session summary; `rag_search` would also be available on demand.

## Token cost & retrieval reachability

| Q | Baseline tok | Triforge tok | Δ | Search recall@5 | Prelude recall | **Any path** | Search ms | Disk |
|---|---:|---:|---:|:---:|:---:|:---:|---:|---:|
| Q1 | 25 | 168 | +143 | ❌ | ✅ | ✅ | 114.5 ms | 24.5 KB |
| Q2 | 12 | 142 | +130 | ✅ | ❌ | ✅ | 2.8 ms | 24.0 KB |
| Q3 | 14 | 146 | +132 | ❌ | ✅ | ✅ | 2.6 ms | 24.2 KB |
| Q4 | 15 | 148 | +133 | ✅ | ❌ | ✅ | 2.6 ms | 24.2 KB |

### Aggregate

- **Mean prompt cost:** baseline 16 tok → triforge 151 tok (+134 tok / +815%)
- **rag_search recall@5:** 2/4 (50%)
- **Prelude recall:** 2/4 (50%)
- **Any-path recall (prelude OR rag_search):** **4/4 (100%)**
- **Mean latency:** index 1 ms · prelude 0 ms · search 30.6 ms

### Read-out

triforge's value isn't only `rag_search`. The **SessionStart prelude**
front-loads the most recent ~140 tokens of summary into Claude's context
unconditionally — that one line is the cheapest recall mechanism we have,
and it covers most "what did we decide last week" questions on its own.
`rag_search` then handles the deeper queries that the summary doesn't
touch.

The "any path" column is the metric that matters for the user: can the
agent answer at all, given everything triforge made available? On this
4-question seed, that's **4/4**.

## Top-5 chunks per question (transparency)

### Q1 — top-5 chunks

  1. `What did we decide about the task status field two sessions ago, and is there a planned endpoint we still need to implem`...
  2. `Plan: POST /tasks/{id}/done that flips `done=1`. Returns 404 if id missing. Will implement next session — need first to `...
  3. `We need an endpoint to mark tasks done.`...
  4. `Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?`...
  5. `Where do task descriptions live? I see only title.`...
### Q2 — top-5 chunks

  1. `Why don't we have a description column on tasks yet?`...
  2. `Today only `title` (TEXT NOT NULL). We deferred `description` because the v1 spec didn't require multi-line bodies. We c`...
  3. `Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?`...
  4. `Add the column to the schema then.`...
  5. `Where do task descriptions live? I see only title.`...
### Q3 — top-5 chunks

  1. `Reminder: how should I write a query that filters only unfinished tasks?`...
  2. `Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?`...
  3. `We need an endpoint to mark tasks done.`...
  4. `Plan: POST /tasks/{id}/done that flips `done=1`. Returns 404 if id missing. Will implement next session — need first to `...
  5. `Where do task descriptions live? I see only title.`...
### Q4 — top-5 chunks

  1. `When we add multi-line task descriptions later, do we need a migration?`...
  2. `Today only `title` (TEXT NOT NULL). We deferred `description` because the v1 spec didn't require multi-line bodies. We c`...
  3. `Where do task descriptions live? I see only title.`...
  4. `We need an endpoint to mark tasks done.`...
  5. `Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?`...

## LLM-driven measurements

_No `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set — LLM layer skipped._

To enable, export a key and re-run:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python benchmark/real_benchmark.py
```


## Raw JSON

`2026-05-06-real-benchmark.json`
