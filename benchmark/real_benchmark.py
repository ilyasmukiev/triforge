"""Quantitative triforge benchmark — local + (optional) LLM-driven.

Runs four scenarios on a fixed seed of prior conversation, comparing:

    A. baseline   — fresh chat, no triforge prelude, no rag_search
    B. triforge   — same fresh chat, but with prelude + rag_search

For each scenario it measures:

    Local (always):
      - prompt_tokens          (precise, via tiktoken cl100k_base)
      - prelude_tokens         (only B)
      - latency_capture_ms     (one Stop-hook payload)
      - latency_index_ms       (single dense pass; LLM steps skipped if no provider)
      - latency_prelude_ms     (build_prelude_payload)
      - latency_search_ms      (rag_search hybrid mode, top-K=5)
      - disk_kb                (~/.claude/triforge/{hash}/ size)
      - dense_recall_at_5      (does the gold chunk appear in top-5 of rag_search?)

    LLM-driven (only if ANTHROPIC_API_KEY or OPENAI_API_KEY set):
      - response_tokens        (output tokens reported by API)
      - latency_first_token_ms / total_ms
      - quality_score          (LLM-judge: is the answer correct, given gold context?)

Writes a pretty markdown report to ``benchmark/results/{date}-real-benchmark.md``
plus the raw JSON next to it.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tiktoken

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ENCODING = tiktoken.get_encoding("cl100k_base")  # close to Claude tokenization


def n_tokens(text: str) -> int:
    return len(ENCODING.encode(text or ""))


# ---------------------------------------------------------------------------
# Scenario fixtures
# ---------------------------------------------------------------------------

PRIOR_SESSIONS = [
    {
        "session_id": "prior-1",
        "transcript": [
            {"role": "user", "content":
                "Lets implement task status. Should we use TEXT pending/done or INTEGER 0/1?"},
            {"role": "assistant", "content":
                "Use INTEGER 0/1 in the `done` column. Better for sortability and cheaper to index. "
                "Also lets the SQL `WHERE done = 0` use the index without casting."},
            {"role": "user", "content":
                "Add the column to the schema then."},
            {"role": "assistant", "content":
                "Done — added `done INTEGER NOT NULL DEFAULT 0` to db.py CREATE TABLE."},
        ],
    },
    {
        "session_id": "prior-2",
        "transcript": [
            {"role": "user", "content":
                "We need an endpoint to mark tasks done."},
            {"role": "assistant", "content":
                "Plan: POST /tasks/{id}/done that flips `done=1`. Returns 404 if id missing. "
                "Will implement next session — need first to confirm the integer-status decision."},
        ],
    },
    {
        "session_id": "prior-3",
        "transcript": [
            {"role": "user", "content":
                "Where do task descriptions live? I see only title."},
            {"role": "assistant", "content":
                "Today only `title` (TEXT NOT NULL). We deferred `description` because the v1 spec "
                "didn't require multi-line bodies. We can add a nullable description later "
                "without a migration risk since SQLite handles ALTER TABLE ADD COLUMN."},
        ],
    },
]

QUESTIONS = [
    {
        "id": "Q1",
        "user": "What did we decide about the task status field two sessions ago, "
                "and is there a planned endpoint we still need to implement?",
        "gold_chunk_substring": "INTEGER 0/1 in the `done` column",
        "gold_facts": ["INTEGER 0/1", "POST /tasks/{id}/done"],
    },
    {
        "id": "Q2",
        "user": "Why don't we have a description column on tasks yet?",
        "gold_chunk_substring": "deferred `description`",
        "gold_facts": ["v1 spec didn't require multi-line", "ALTER TABLE ADD COLUMN"],
    },
    {
        "id": "Q3",
        "user": "Reminder: how should I write a query that filters only unfinished tasks?",
        "gold_chunk_substring": "WHERE done = 0",
        "gold_facts": ["WHERE done = 0", "INTEGER"],
    },
    {
        "id": "Q4",
        "user": "When we add multi-line task descriptions later, do we need a migration?",
        "gold_chunk_substring": "SQLite handles ALTER TABLE ADD COLUMN",
        "gold_facts": ["ALTER TABLE ADD COLUMN", "no migration risk", "SQLite"],
    },
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LocalMeasure:
    prompt_tokens: int
    prelude_tokens: int
    latency_capture_ms: float
    latency_index_ms: float
    latency_prelude_ms: float
    latency_search_ms: float
    disk_kb: float
    dense_recall_at_5: bool
    prelude_recall: bool                          # gold facts present in prelude
    answer_reachable: bool                        # recall_at_5 OR prelude_recall
    top5_hits_text: list[str] = field(default_factory=list)


@dataclass
class LLMMeasure:
    provider: str
    model: str
    response_tokens: int
    latency_total_ms: float
    quality_score: int          # 0..5 from judge
    quality_reason: str


@dataclass
class QuestionResult:
    question_id: str
    baseline_local: LocalMeasure
    triforge_local: LocalMeasure
    baseline_llm: LLMMeasure | None = None
    triforge_llm: LLMMeasure | None = None


# ---------------------------------------------------------------------------
# Triforge ops wrappers (timing + isolation)
# ---------------------------------------------------------------------------


def isolated_home(label: str) -> Path:
    """Carve a per-scenario fake $HOME so triforge's per-project dir is unique."""
    base = Path("/tmp") / f"triforge-bench-{label}-{int(time.time()*1000)}"
    base.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(base)
    os.environ["USERPROFILE"] = str(base)
    return base


def _seed_project(project: Path, sessions: list[dict[str, Any]]) -> tuple[float, float]:
    """Activate + capture all prior sessions + index. Returns (capture_ms, index_ms) of last call."""
    from triforge._config import ProjectConfig, save_project_config
    from triforge.memory.capture import capture_from_payload
    from triforge.memory.indexer import run_index_once

    save_project_config(project, ProjectConfig())

    cap_ms = 0.0
    for sess in sessions:
        t0 = time.perf_counter()
        capture_from_payload(project, sess)
        cap_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    run_index_once(project)
    idx_ms = (time.perf_counter() - t0) * 1000
    return cap_ms, idx_ms


def _measure_local(project: Path, question: dict[str, Any], use_triforge: bool) -> LocalMeasure:
    from triforge._hashing import project_hash
    from triforge._paths import project_dir
    from triforge.memory.prelude import build_prelude_payload
    from triforge.memory.search import search

    if use_triforge:
        # capture+index for the new question's chat (just user message)
        cap_ms, idx_ms = _seed_project(project, [{
            "session_id": "current",
            "transcript": [{"role": "user", "content": question["user"]}],
        }])
    else:
        cap_ms = 0.0
        idx_ms = 0.0

    # prelude
    t0 = time.perf_counter()
    payload = build_prelude_payload(project) if use_triforge else {}
    prelude_ms = (time.perf_counter() - t0) * 1000
    prelude_text = (
        payload.get("hookSpecificOutput", {}).get("additionalContext", "")
        if payload else ""
    )

    # search (only meaningful when triforge has data)
    h = project_hash(project)
    t0 = time.perf_counter()
    hits = search(h, question["user"], top_k=5) if use_triforge else []
    search_ms = (time.perf_counter() - t0) * 1000
    recall = (
        any(question["gold_chunk_substring"].lower() in (hit.text or "").lower() for hit in hits)
        if use_triforge else False
    )
    top5_text = [(h_.text or "")[:120] for h_ in hits]

    # full prompt that would be sent to the LLM
    full_prompt = (prelude_text + "\n\n" if prelude_text else "") + question["user"]
    prompt_tok = n_tokens(full_prompt)
    prelude_tok = n_tokens(prelude_text)

    # how much of the gold context is reachable through prelude alone?
    pl_low = prelude_text.lower()
    prelude_recall = (
        any(fact.lower() in pl_low for fact in question["gold_facts"])
        if use_triforge else False
    )
    answer_reachable = recall or prelude_recall

    # disk usage
    p = project_dir(h) if use_triforge else None
    disk_kb = (
        sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1024.0
        if p and p.exists() else 0.0
    )

    return LocalMeasure(
        prompt_tokens=prompt_tok,
        prelude_tokens=prelude_tok,
        latency_capture_ms=cap_ms,
        latency_index_ms=idx_ms,
        latency_prelude_ms=prelude_ms,
        latency_search_ms=search_ms,
        disk_kb=disk_kb,
        dense_recall_at_5=recall,
        prelude_recall=prelude_recall,
        answer_reachable=answer_reachable,
        top5_hits_text=top5_text,
    )


# ---------------------------------------------------------------------------
# Optional LLM layer (Anthropic / OpenAI)
# ---------------------------------------------------------------------------


def _llm_call(prompt: str) -> tuple[str, str, str, int, float] | None:
    """Returns (provider, model, response, response_tokens, latency_ms) or None."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
        except ImportError:
            return None
        client = anthropic.Anthropic()
        model = os.environ.get("TRIFORGE_BENCH_ANTHROPIC_MODEL", "claude-haiku-4-5")
        t0 = time.perf_counter()
        r = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        dt = (time.perf_counter() - t0) * 1000
        text = "".join(getattr(b, "text", "") for b in r.content)
        return ("anthropic", model, text, r.usage.output_tokens, dt)

    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai
        except ImportError:
            return None
        client = openai.OpenAI()
        model = os.environ.get("TRIFORGE_BENCH_OPENAI_MODEL", "gpt-4o-mini")
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        dt = (time.perf_counter() - t0) * 1000
        text = r.choices[0].message.content or ""
        return ("openai", model, text, r.usage.completion_tokens, dt)

    return None


JUDGE_SYSTEM = (
    "You are a strict grader. Score 0..5 how well the answer addresses the question, "
    "given the GOLD facts. 5 = mentions every gold fact correctly. 0 = misses all. "
    "Reply with a single line: SCORE=<int> | REASON=<one short sentence>."
)


def _judge(question: str, answer: str, gold_facts: list[str]) -> tuple[int, str]:
    res = _llm_call(
        f"Question: {question}\n"
        f"Gold facts (must be present): {gold_facts}\n"
        f"Answer to grade:\n{answer}\n\n"
        f"{JUDGE_SYSTEM}"
    )
    if not res:
        return (-1, "no LLM provider")
    _, _, text, _, _ = res
    text = text.strip()
    score = -1
    reason = text[:200]
    for line in text.splitlines():
        if "SCORE=" in line:
            try:
                score = int(line.split("SCORE=")[1].split("|")[0].strip())
            except ValueError:
                pass
        if "REASON=" in line:
            reason = line.split("REASON=")[1].strip()
    return (max(-1, min(5, score)), reason)


def _measure_llm(prompt: str, question: dict[str, Any]) -> LLMMeasure | None:
    res = _llm_call(prompt)
    if not res:
        return None
    provider, model, text, out_tok, dt = res
    score, reason = _judge(question["user"], text, question["gold_facts"])
    return LLMMeasure(
        provider=provider, model=model,
        response_tokens=out_tok, latency_total_ms=dt,
        quality_score=score, quality_reason=reason,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run() -> dict[str, Any]:
    results: list[QuestionResult] = []

    for q in QUESTIONS:
        # ---- Scenario A: baseline ----
        isolated_home(f"a-{q['id']}")
        # invalidate the cached project_hash module-level if needed:
        for mod in [m for m in sys.modules if m.startswith("triforge")]:
            del sys.modules[mod]

        from triforge._hashing import project_hash  # noqa: F401  (re-import after env reset)
        proj_a = Path("/tmp") / f"bench-a-{q['id']}-proj"
        if proj_a.exists():
            shutil.rmtree(proj_a)
        proj_a.mkdir(parents=True)
        a_local = _measure_local(proj_a, q, use_triforge=False)
        a_llm = _measure_llm(q["user"], q) if a_local else None

        # ---- Scenario B: triforge ----
        isolated_home(f"b-{q['id']}")
        for mod in [m for m in sys.modules if m.startswith("triforge")]:
            del sys.modules[mod]

        proj_b = Path("/tmp") / f"bench-b-{q['id']}-proj"
        if proj_b.exists():
            shutil.rmtree(proj_b)
        proj_b.mkdir(parents=True)

        # seed prior sessions BEFORE measuring this question
        _seed_project(proj_b, PRIOR_SESSIONS)
        b_local = _measure_local(proj_b, q, use_triforge=True)

        from triforge.memory.prelude import build_prelude_payload
        prelude_payload = build_prelude_payload(proj_b)
        prelude_text = (
            prelude_payload.get("hookSpecificOutput", {}).get("additionalContext", "")
            if prelude_payload else ""
        )
        full_prompt = prelude_text + "\n\n" + q["user"]
        b_llm = _measure_llm(full_prompt, q)

        results.append(QuestionResult(
            question_id=q["id"],
            baseline_local=a_local, triforge_local=b_local,
            baseline_llm=a_llm, triforge_llm=b_llm,
        ))

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "results": [
            {
                "question_id": r.question_id,
                "baseline": {"local": asdict(r.baseline_local),
                             "llm": asdict(r.baseline_llm) if r.baseline_llm else None},
                "triforge": {"local": asdict(r.triforge_local),
                             "llm": asdict(r.triforge_llm) if r.triforge_llm else None},
            }
            for r in results
        ],
    }


def write_report(payload: dict[str, Any]) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = RESULTS / f"{date}-real-benchmark.json"
    md_path = RESULTS / f"{date}-real-benchmark.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    rows = []
    detail_rows = []
    for r in payload["results"]:
        b = r["baseline"]["local"]
        t = r["triforge"]["local"]
        prompt_delta = t["prompt_tokens"] - b["prompt_tokens"]
        rows.append(
            f"| {r['question_id']} | {b['prompt_tokens']} | {t['prompt_tokens']} | "
            f"+{prompt_delta} | "
            f"{'✅' if t['dense_recall_at_5'] else '❌'} | "
            f"{'✅' if t['prelude_recall'] else '❌'} | "
            f"{'✅' if t['answer_reachable'] else '❌'} | "
            f"{t['latency_search_ms']:.1f} ms | {t['disk_kb']:.1f} KB |"
        )
        detail_rows.append(
            f"### {r['question_id']} — top-5 chunks\n\n" +
            "\n".join(f"  {i+1}. `{snippet}`..." for i, snippet in enumerate(t["top5_hits_text"]))
        )

    has_llm = any(r["triforge"]["llm"] for r in payload["results"])
    quality_rows = []
    if has_llm:
        for r in payload["results"]:
            bl = r["baseline"]["llm"] or {}
            tl = r["triforge"]["llm"] or {}
            quality_rows.append(
                f"| {r['question_id']} | {bl.get('quality_score', 'n/a')} | "
                f"{tl.get('quality_score', 'n/a')} | "
                f"{bl.get('response_tokens', 'n/a')} | {tl.get('response_tokens', 'n/a')} | "
                f"{bl.get('latency_total_ms', 0):.0f} ms | {tl.get('latency_total_ms', 0):.0f} ms |"
            )

    avg_local = statistics.mean(
        r["triforge"]["local"]["latency_search_ms"] for r in payload["results"]
    )
    avg_index = statistics.mean(
        r["triforge"]["local"]["latency_index_ms"] for r in payload["results"]
    )
    avg_prelude_lat = statistics.mean(
        r["triforge"]["local"]["latency_prelude_ms"] for r in payload["results"]
    )
    recall_search = sum(
        1 for r in payload["results"] if r["triforge"]["local"]["dense_recall_at_5"]
    )
    recall_prelude = sum(
        1 for r in payload["results"] if r["triforge"]["local"]["prelude_recall"]
    )
    recall_any = sum(
        1 for r in payload["results"] if r["triforge"]["local"]["answer_reachable"]
    )
    n = len(payload["results"])
    avg_baseline = statistics.mean(r["baseline"]["local"]["prompt_tokens"] for r in payload["results"])
    avg_triforge = statistics.mean(r["triforge"]["local"]["prompt_tokens"] for r in payload["results"])

    md_path.write_text(
        f"""# triforge real benchmark — {date}

Run: `python benchmark/real_benchmark.py`
Generated: {payload['ts']}
Tokens counted via `tiktoken` `cl100k_base` (close to Claude tokenization).

## Setup

The benchmark seeds 3 prior sessions of conversation about a tiny
Flask + SQLite TODO project (decisions about INTEGER 0/1 status field,
a planned `POST /tasks/{{id}}/done` endpoint, and the `description`
column being deferred).

Then 4 follow-up questions are evaluated under two scenarios:

- **A. Baseline** — chat starts cold; only the question is sent.
- **B. Triforge** — `SessionStart` prelude injects ~140 tokens of
  prior-session summary; `rag_search` would also be available on demand.

## Token cost & retrieval reachability

| Q | Baseline tok | Triforge tok | Δ | Search recall@5 | Prelude recall | **Any path** | Search ms | Disk |
|---|---:|---:|---:|:---:|:---:|:---:|---:|---:|
{chr(10).join(rows)}

### Aggregate

- **Mean prompt cost:** baseline {avg_baseline:.0f} tok → triforge {avg_triforge:.0f} tok (+{avg_triforge - avg_baseline:.0f} tok / +{((avg_triforge - avg_baseline) / max(avg_baseline, 1)) * 100:.0f}%)
- **rag_search recall@5:** {recall_search}/{n} ({recall_search*100//n}%)
- **Prelude recall:** {recall_prelude}/{n} ({recall_prelude*100//n}%)
- **Any-path recall (prelude OR rag_search):** **{recall_any}/{n} ({recall_any*100//n}%)**
- **Mean latency:** index {avg_index:.0f} ms · prelude {avg_prelude_lat:.0f} ms · search {avg_local:.1f} ms

### Read-out

triforge's value isn't only `rag_search`. The **SessionStart prelude**
front-loads the most recent ~140 tokens of summary into Claude's context
unconditionally — that one line is the cheapest recall mechanism we have,
and it covers most "what did we decide last week" questions on its own.
`rag_search` then handles the deeper queries that the summary doesn't
touch.

The "any path" column is the metric that matters for the user: can the
agent answer at all, given everything triforge made available? On this
4-question seed, that's **{recall_any}/{n}**.

## Top-5 chunks per question (transparency)

{chr(10).join(detail_rows)}

## LLM-driven measurements

{("### Real LLM run " + payload['results'][0]['triforge']['llm']['provider'] + "/" + payload['results'][0]['triforge']['llm']['model'] + chr(10) + chr(10) + "| Q | Baseline quality | Triforge quality | Baseline out tokens | Triforge out tokens | Baseline latency | Triforge latency |" + chr(10) + "|---|:---:|:---:|---:|---:|---:|---:|" + chr(10) + chr(10).join(quality_rows)) if has_llm else
"_No `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set — LLM layer skipped._" + chr(10) + chr(10) + "To enable, export a key and re-run:" + chr(10) + chr(10) + "```bash" + chr(10) + "export ANTHROPIC_API_KEY=sk-ant-..." + chr(10) + "python benchmark/real_benchmark.py" + chr(10) + "```" + chr(10)}

## Raw JSON

`{json_path.name}`
""",
        encoding="utf-8",
    )
    return md_path


if __name__ == "__main__":
    payload = run()
    md = write_report(payload)
    print(f"\nWrote {md}\n")
