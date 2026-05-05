---
description: Activate triforge per-project chat memory in the current project.
---

You are now executing the `/rag` skill. Your job is to activate **triforge memory** in the current project so that every future chat in this folder is captured, indexed, and made available to new sessions through the MCP tool `rag_search`.

Do all of the steps below in order. After each step, report a single short line confirming success.

## Steps

1. **Detect the project root.** Use the current working directory.

2. **Run the activation command** via Bash:

   ```bash
   triforge install --project-only --here
   ```

   This single command:
   - creates `.triforge/` and `.triforge/config.json` (defaults: local storage, no exclude patterns),
   - writes `.triforge/.gitignore` so memory data never lands in git,
   - writes `.claude/settings.local.json` with three hooks (`SessionStart` / `Stop` / `SessionEnd`) bound to absolute paths so they work on macOS, Linux and Windows,
   - appends a short `## Triforge memory` section to `AGENTS.md` (or `CLAUDE.md` if `AGENTS.md` is missing).

3. **Verify** by running:

   ```bash
   triforge status
   ```

   Print the one-line summary it produces (likely `chats: 0`, `vectors: 0` — fresh activation).

4. **Tell the user**:

   > Triforge memory activated for this project. From the next chat onward, our conversations will be captured and indexed automatically. You can search past conversations any time with the MCP tool `rag_search`.

## If `triforge` is not on PATH

Print this exact instruction and stop:

> `triforge` is not installed yet. Run **`pipx install triforge`** (or `pip install --user triforge`) and then re-run `/rag`.

Do not attempt to install Python packages yourself.
