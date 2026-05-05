"""triforge command-line interface."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from triforge import __version__

app = typer.Typer(
    name="triforge",
    help="One install — three dimensions of intelligence for Claude Code.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(f"triforge {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_cb,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """Root callback (declared so --version works as a global flag)."""


@app.command()
def install(
    project_only: Annotated[
        bool,
        typer.Option(
            "--project-only",
            help="Skip global install; configure the current project only.",
        ),
    ] = False,
    here: Annotated[
        bool,
        typer.Option(
            "--here",
            help="With --project-only, use the current working directory as project root.",
        ),
    ] = False,
) -> None:
    """Register MCP servers + slash-command globally; or activate per-project with --project-only."""
    from triforge.installer import install_global, install_project_here

    if project_only:
        if not here:
            typer.echo("Use --here together with --project-only to confirm the cwd.", err=True)
            raise typer.Exit(2)
        install_project_here(Path.cwd())
        typer.echo("triforge: project memory activated")
    else:
        install_global()
        typer.echo("triforge: global install complete (MCP servers + /rag slash-command)")


@app.command()
def uninstall() -> None:
    """Undo `triforge install`: remove our MCP entries and slash-command file."""
    from triforge.installer import _slash_command_path, remove_mcp_servers

    removed = remove_mcp_servers()
    cmd = _slash_command_path()
    if cmd.exists():
        cmd.unlink()
    typer.echo(f"removed servers: {removed}; slash-command deleted: {cmd}")


@app.command()
def status(
    project: Annotated[
        Path | None, typer.Option(help="Project path (default: cwd)")
    ] = None,
) -> None:
    """Show memory statistics for a project."""
    from triforge._config import is_project_activated
    from triforge._hashing import project_hash
    from triforge._paths import chats_jsonl, summary_md
    from triforge.memory.store import load_all_vectors

    proj = (project or Path.cwd()).resolve()
    if not is_project_activated(proj):
        typer.echo(
            f"triforge: project not activated ({proj}). Run /rag inside it to enable memory."
        )
        return
    h = project_hash(proj)
    n_chats = (
        sum(1 for line in chats_jsonl(h).read_text(encoding="utf-8").splitlines() if line.strip())
        if chats_jsonl(h).exists()
        else 0
    )
    n_vec = len(load_all_vectors(h))
    summary_size = summary_md(h).stat().st_size if summary_md(h).exists() else 0
    console.print(f"[bold]project:[/bold] {proj}")
    console.print(f"[bold]hash:[/bold] {h}")
    console.print(f"[bold]chats:[/bold] {n_chats}")
    console.print(f"[bold]indexed vectors:[/bold] {n_vec}")
    console.print(f"[bold]summary size:[/bold] {summary_size} bytes")


@app.command()
def dump(
    project: Annotated[
        Path | None, typer.Option(help="Project path (default: cwd)")
    ] = None,
) -> None:
    """Print summary.md for a project."""
    from triforge._config import is_project_activated
    from triforge._hashing import project_hash
    from triforge.memory.store import read_summary_tail

    proj = (project or Path.cwd()).resolve()
    if not is_project_activated(proj):
        typer.echo("triforge: project not activated", err=True)
        raise typer.Exit(1)
    body = read_summary_tail(project_hash(proj), max_chars=1_000_000)
    typer.echo(body)


@app.command()
def purge(
    project: Annotated[
        Path | None, typer.Option(help="Project path (default: cwd)")
    ] = None,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation")] = False,
) -> None:
    """Wipe the per-project memory directory."""
    import shutil as _sh

    from triforge._hashing import project_hash
    from triforge._paths import project_dir

    proj = (project or Path.cwd()).resolve()
    h = project_hash(proj)
    target = project_dir(h)
    if not yes and not typer.confirm(f"Delete {target}?"):
        typer.echo("aborted")
        raise typer.Exit(1)
    _sh.rmtree(target, ignore_errors=True)
    typer.echo(f"purged {target}")


@app.command()
def capture(
    project: Annotated[
        Path, typer.Option(help="Project path (passed by Claude Code Stop hook)")
    ],
) -> None:
    """Stop-hook entry point: append latest exchange to chats.jsonl."""
    from triforge.memory.capture import capture_from_stdin

    n = capture_from_stdin(project)
    typer.echo(f"captured {n} record(s)")


@app.command()
def index(
    project: Annotated[Path, typer.Option(help="Project path")],
    background: Annotated[
        bool,
        typer.Option(
            "--background",
            help="Detach and return immediately; child indexes in the background.",
        ),
    ] = False,
) -> None:
    """SessionEnd-hook entry point: index new chats.jsonl entries."""
    from triforge.memory.indexer import run_index_once, spawn_index_background

    if background:
        spawn_index_background(project)
        typer.echo("indexer detached")
        return
    n = run_index_once(project)
    typer.echo(f"indexed {n} record(s)")


@app.command()
def prelude(
    project: Annotated[Path, typer.Option(help="Project path")],
) -> None:
    """SessionStart-hook entry point: emit additionalContext JSON on stdout."""
    import json as _json

    from triforge.memory.prelude import build_prelude_payload

    payload = build_prelude_payload(project)
    if payload:
        typer.echo(_json.dumps(payload))


@app.command()
def migrate(
    to: Annotated[
        str, typer.Option("--to", help="Target backend. Currently only 'insforge' is supported.")
    ] = "insforge",
    database_url: Annotated[
        str | None,
        typer.Option(
            "--database-url",
            envvar="DATABASE_URL",
            help="PostgreSQL URL with pgvector. Defaults to $DATABASE_URL.",
        ),
    ] = None,
    project: Annotated[
        Path | None, typer.Option(help="Project path (default: cwd)")
    ] = None,
    truncate: Annotated[
        bool,
        typer.Option(
            "--truncate",
            help="Drop all rows for this project before re-inserting (idempotent rebuild).",
        ),
    ] = False,
) -> None:
    """Export per-project memory into a PostgreSQL+pgvector store (e.g. InsForge)."""
    if to.lower() != "insforge":
        typer.echo(f"unknown target backend: {to!r}", err=True)
        raise typer.Exit(2)
    if not database_url:
        typer.echo(
            "Need a PostgreSQL URL. Pass --database-url or set DATABASE_URL.",
            err=True,
        )
        raise typer.Exit(2)
    proj = (project or Path.cwd()).resolve()

    from triforge.memory.insforge_export import export_project

    summary = export_project(proj, database_url=database_url, truncate=truncate)
    console.print(
        f"[green]migrated[/green] project [bold]{summary.project_hash}[/bold]: "
        f"{summary.n_chats} chats, {summary.n_vectors} vectors, "
        f"{summary.n_summary_bytes} bytes of summary."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
