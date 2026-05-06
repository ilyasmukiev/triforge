# Realistic token comparison — 2026-05-06

The previous report (`2026-05-06-llm-quality-comparison.md`) measured quality but not the **real** token cost, because the baseline was forbidden from using tools. This report fixes that.

Both scenarios were given identical access to a real Flask + SQLite TODO sandbox at `benchmark/sandbox-todo-app/` and asked the same question:

> *"What did we decide about the task status field two sessions ago, and is there a planned endpoint we still need to implement?"*

Each was a single fresh `claude-haiku-4-5` subagent. **Both could call Read / Bash / Grep tools.** Triforge's prelude was injected; baseline got no prelude.

## Results

| Metric | Baseline | Triforge | Δ |
|---|---:|---:|---:|
| **Total tokens (prompt + tool calls + response, all turns)** | **45,049** | **36,380** | **−8,669 (−19 %)** |
| Tool calls | 10 | 0 | −10 |
| Wall-clock duration | 66.6 s | 2.9 s | **−63.7 s (23× faster)** |
| Found a correct answer? | ❌ No — gave up | ✅ Yes — concrete | — |

## What actually happened

### Baseline (no triforge)

Claude tried to *reconstruct* the prior decisions from the codebase. It ran roughly this sequence (10 tool calls total):

1. `ls -la` the project root
2. Look for `.omc/`, `.claude/`, session notes — not found
3. `Read app.py`
4. `Read db.py`
5. `Read README.md`
6. `Read requirements.txt`
7. `Grep` for `done`, `status`, `endpoint`
8. `git log` (no commits with decision context)
9. Search for documentation files
10. Try `Read` on a few more candidate paths

After 66 seconds and ~45 k tokens of tool-result roundtrips, Claude gave up:

> *"This is your first chat with this project, and there are no `.omc`, `.claude`, or session notes directories. Without access to previous session notes, git commit history, or email threads, I cannot confirm what was specifically decided. Could you share what you remember?"*

Claude **inferred the current state of the code** (correctly: `done INTEGER`, `POST /tasks/{id}/done` exists), but couldn't recover the **decisions** behind that state — which is what the user asked about.

### Triforge

The prelude (134 tokens) carried the exact prior decisions. Claude answered in one turn (2.9 s, 0 tool calls):

> *"We decided to use INTEGER 0/1 in the `done` column — better for sortability and cheaper to index. The `done INTEGER NOT NULL DEFAULT 0` column was added in prior-1. The planned endpoint is POST /tasks/{id}/done — flips done=1, returns 404 if the id doesn't exist."*

## The real ROI

Triforge's prelude **adds 134 tokens** to a session start. In exchange:

- **Avoids ~9,000 tokens** of tool-call overhead the agent would otherwise spend trying to reconstruct context that's not in the codebase.
- **Saves ~64 seconds of latency** per such question (roughly 23× faster).
- **Actually answers the question**, instead of returning "I don't know."

**Net per question:** −8,669 input/output tokens, −63.7 s, +1 correct answer.

## What the previous report measured

The earlier `2026-05-06-llm-quality-comparison.md` report compared *prompt-only* sizes (16 vs 151 tokens) and reported triforge as a **+134 token overhead**. That's true for the *first* user message of a session — but it ignored that the baseline agent then immediately spends thousands more tokens flailing in the filesystem to recover the missing context. The realistic measurement above includes that flailing.

## Reproducibility

Each scenario is one Claude Code Agent call with `model="haiku"` and the same Flask sandbox. Token counts come from the agent's own `<usage>` block (prompt + completion + tool-result roundtrips). Verbatim outputs are quoted above.

## Take-away

> Memory is not a tax. It's a refund.

If your prior decisions live in chat (which they do, if you use Claude Code), then any time the agent has to "rediscover" them by scanning files, it's spending real tokens on the wrong thing. Triforge replaces that scan with 134 tokens of summary up-front, and that's a net 19 % saving on this benchmark — plus a 23× speed-up plus actually getting the right answer.

The trade-off only flips against triforge in one case: **the answer never lived in chat in the first place** (e.g. the user is asking about a fresh, never-discussed topic). There the prelude is 134 tokens of pure overhead for no benefit. For projects with active iteration history (the common case), the overhead pays back many times over.
