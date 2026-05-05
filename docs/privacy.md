# Privacy

triforge captures conversations to a per-project store on disk. This page is a **plain-language guide** to what is stored, what is stripped, and how to delete it.

## What is captured

- Every **user message** and **assistant text response** that flows through Claude Code while the project is `/rag`-activated.
- Tool calls (Edit, Read, Bash...), tool results, and the agent's hidden thinking blocks are **not** captured.

## Where it lives

In **the user's home directory**, never inside the project tree:

```text
~/.claude/triforge/<sha256(project_path)[:12]>/
   ├─ chats.jsonl     ← raw redacted text, append-only
   ├─ vectors/        ← parquet shards of dense embeddings
   ├─ summary.md      ← short summaries of past sessions
   ├─ kg.pkl          ← knowledge graph (only if an LLM provider is up)
   └─ state.json      ← indexer cursor
```

Plus a project-side marker:

```text
your-project/.triforge/config.json    ← marker only, no content
your-project/.triforge/.gitignore     ← prevents accidental commit
```

The `.gitignore` excludes everything in `.triforge/`, so even the marker won't leak.

## Two-stage redaction

### Stage 1 — regex (always on)

Built-in patterns covering the obvious:

| Pattern | Catches |
|---|---|
| `env_var_secret` | `OPENAI_API_KEY=...`, `MY_TOKEN=...`, `PASSWORD=...` etc. |
| `bearer_token` | `Authorization: Bearer eyJabc...` |
| `password_assignment` | `password = "..."`, `password: "..."` |
| `jwt` | full three-part JWTs |
| `openai_secret` | `sk-...` keys |
| `aws_access_key` | `AKIA[A-Z0-9]{16}` |
| `private_key_block` | `-----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----` |

Plus any user patterns from `.triforge/config.json`'s `exclude` array. Matches are replaced with `[REDACTED]` before anything is written to disk.

### Stage 2 — LLM cleaner (only if a provider is configured)

If after stage 1 a record still contains heuristic trigger words (`secret`, `password`, `passwd`, `token`, `auth`, `api_key`, `apikey`, `private_key`, `private key`, `bearer`, `credential`, `ssh-`), triforge sends the chunk to a **separate LLM call** with this prompt:

> You are a privacy filter. Read the user's text. Replace any remaining secrets, passwords, API tokens, private keys, personal addresses, credit-card numbers or similar sensitive strings with the literal text `[REDACTED]`. Preserve everything else verbatim. Reply with ONLY the cleaned text — no preamble, no quoting, no explanation.

The provider is selected by `_llm.get_provider()`:

1. `ANTHROPIC_API_KEY` set → Anthropic (`claude-haiku-4-5`).
2. `OPENAI_API_KEY` set → OpenAI (`gpt-4o-mini`).
3. Local Ollama daemon reachable at `OLLAMA_HOST` (default `http://localhost:11434`) → Ollama (`qwen2.5:7b`).
4. None of the above → stage 2 is **skipped silently**; you keep stage 1 only.

Force a particular choice (or disable) with `TRIFORGE_LLM_PROVIDER=anthropic|openai|ollama|none`.

## What never leaves your machine

- **Capture, indexing, dense search, BM25 search, graph PPR retrieval** — fully local, no network.
- **Models** — `model2vec` runs on CPU from a one-time HuggingFace download.

The cloud goes out **only** when stage 2 cleaning, the LLM summary, or LLM OpenIE fires — i.e. only when you've intentionally configured a provider key. With no provider, the only outbound call triforge ever makes is the initial HuggingFace model download.

## Inspecting and deleting

```bash
triforge status            # how many chats, vectors, summary size
triforge dump              # print the entire summary.md
triforge purge -y          # wipe ALL data for this project
```

To remove only specific patterns from existing records you can edit `chats.jsonl` directly — it's a plain JSONL file. Then re-run `triforge index` to rebuild vectors.

## Source code

| Concern | File |
|---|---|
| Built-in regexes | [`src/triforge/_privacy.py`](https://github.com/ilyasmukiev/triforge/blob/main/src/triforge/_privacy.py) |
| LLM cleaner | [`src/triforge/_privacy_llm.py`](https://github.com/ilyasmukiev/triforge/blob/main/src/triforge/_privacy_llm.py) |
| Capture pipeline | [`src/triforge/memory/capture.py`](https://github.com/ilyasmukiev/triforge/blob/main/src/triforge/memory/capture.py) |
