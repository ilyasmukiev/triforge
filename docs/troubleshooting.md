# Troubleshooting

## `triforge: command not found` after `pipx install`

`pipx` puts scripts in `~/.local/bin` (Unix) or `%USERPROFILE%\.local\bin` (Windows). Make sure that's on your PATH:

=== "macOS / Linux"
    ```bash
    pipx ensurepath
    # then open a new shell
    ```

=== "Windows (PowerShell)"
    ```powershell
    pipx ensurepath
    # close and reopen PowerShell
    ```

## `/rag` says "triforge is not on PATH"

Same root cause as above — Claude Code's shell hooks don't see your interactive shell's PATH. After `pipx ensurepath`, restart Claude Code, then re-run `/rag`.

## Hooks don't fire — no chats are captured

Verify the project marker exists:

```bash
ls .triforge/config.json
ls .claude/settings.local.json
```

If both files are present but nothing is captured, run a manual capture:

```bash
echo '{"session_id":"manual","transcript":[{"role":"user","content":"test"}]}' \
  | triforge capture --project="$PWD"
triforge status
```

`status` should now show 1 chat. If yes, the issue is hook wiring — check `.claude/settings.local.json` exists and is valid JSON. Re-running `/rag` rebuilds it.

## Indexer never runs

`SessionEnd` fires on Claude Code session exit. To force an immediate index:

```bash
triforge index --project="$PWD"
```

If that hangs, the model download may be slow. Re-run with TRACE:

```bash
TRIFORGE_LLM_PROVIDER=none triforge index --project="$PWD"
```

## "ModuleNotFoundError: No module named 'scipy'" during graph search

Harmless — networkx prefers scipy for PPR but triforge ships a pure-Python fallback. The exception is caught and the fallback runs automatically. If you still get a stack trace, please [open an issue](https://github.com/ilyasmukiev/triforge/issues).

## HuggingFace download is slow / fails behind a proxy

The first run downloads `minishlab/potion-base-8M` (~30 MB). Set a token + mirror:

```bash
export HF_TOKEN=<your-token>
export HF_ENDPOINT=https://hf-mirror.com
```

## Windows: "OSError: [WinError 1450] Insufficient system resources"

That comes from Windows file-locking on very-many concurrent `chats.jsonl` writes. The defaults are conservative; if you see it, increase `portalocker` retries via:

```powershell
$env:PORTALOCKER_RETRIES = 30
```

## InsForge migrate fails with "extension vector does not exist"

Your PostgreSQL doesn't have pgvector. Either use the InsForge docker-compose (it's pre-installed), or:

```sql
CREATE EXTENSION vector;
```

## "triforge dump" prints nothing

You haven't indexed yet. After at least one `Stop`+`SessionEnd` cycle, `summary.md` will populate. Force it:

```bash
triforge index --project="$PWD"
triforge dump
```

## Resetting everything

```bash
triforge purge -y          # wipe one project
triforge uninstall         # remove MCP entries + slash-command
pipx uninstall triforge
```

## Still stuck?

Open an issue with:

- `triforge --version`
- `triforge status` output
- `cat ~/.claude.json | python -m json.tool | head -40`
- Your OS + Python version
