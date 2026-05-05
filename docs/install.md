# Install

## Requirements

- **Python ≥ 3.10** (3.10, 3.11, 3.12, 3.13 all tested via CI matrix)
- **[Claude Code CLI](https://docs.claude.com/en/docs/claude-code)** installed and authenticated
- **macOS, Linux, or Windows**
- (optional) **API key** for Anthropic, OpenAI, or a local Ollama daemon — without one, triforge works in dense-only mode

## Recommended: pipx

[`pipx`](https://pipx.pypa.io/) keeps triforge isolated from your project venvs:

```bash
pipx install triforge
triforge install
```

What `triforge install` does:

1. Patches `~/.claude.json` to register **three MCP servers** (idempotent — re-running won't duplicate; preserves any user-added servers).
2. Writes `~/.claude/commands/rag.md` (the `/rag` slash-command body).
3. Appends a short section to `~/.claude/CLAUDE.md` so every Claude session knows the three MCPs are available.

## Alternative: pip

```bash
pip install --user triforge
~/.local/bin/triforge install
```

## Optional extras

```bash
# Enable summary/OpenIE/cleaner via cloud LLMs:
pipx install 'triforge[llm]'

# Add the InsForge migrate target:
pipx install 'triforge[insforge]'

# Build docs locally:
pipx install 'triforge[docs]'
```

## Per-project activation

Inside any project folder, run:

```text
> /rag
```

(in a Claude Code session). This invokes the slash-command body — Claude executes `triforge install --project-only --here`, which writes:

- `.triforge/config.json` — the marker file (default storage `local`, no exclude patterns).
- `.triforge/.gitignore` — so the marker dir never leaks into the project's git history.
- `.claude/settings.local.json` — three hooks (`SessionStart`, `Stop`, `SessionEnd`) bound to the absolute path of the `triforge` binary.
- A `## Triforge memory` section appended to `AGENTS.md` (or `CLAUDE.md` if `AGENTS.md` is absent).

From the next chat onward, capture/index/retrieve happens automatically.

## Verify

```bash
triforge --version
triforge --help
triforge status                # in your project folder
```

## Uninstall

```bash
triforge uninstall    # removes our MCP entries from ~/.claude.json + the slash-command file
pipx uninstall triforge
```

To wipe a single project's memory:

```bash
cd your-project
triforge purge -y     # removes ~/.claude/triforge/<project-hash>/
```

Per-project marker files (`.triforge/`, `.claude/settings.local.json`) stay in the project tree — delete them manually if you want to fully detach.
