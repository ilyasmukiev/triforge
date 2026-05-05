"""FastMCP server exposing the `rag_search` tool."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from triforge._hashing import project_hash
from triforge.memory.search import search

mcp = FastMCP("triforge-memory")


def rag_search_impl(
    query: str,
    project_path: str | None = None,
    top_k: int = 5,
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid",
) -> list[dict[str, Any]]:
    """Pure-Python implementation. The MCP tool wraps this."""
    proj = Path(project_path) if project_path else Path.cwd()
    h = project_hash(proj)
    hits = search(h, query, top_k=top_k, mode=mode)
    return [asdict(h_) for h_ in hits]


@mcp.tool()
def rag_search(
    query: str,
    project_path: str | None = None,
    top_k: int = 5,
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid",
) -> list[dict[str, Any]]:
    """Search the project's chat memory.

    Args:
        query: natural-language search string.
        project_path: absolute project path; defaults to the current working directory.
        top_k: maximum results.
        mode: 'hybrid' (default), 'dense', or 'bm25'.
    """
    return rag_search_impl(
        query=query, project_path=project_path, top_k=top_k, mode=mode
    )


def main() -> None:
    """Entry point for `triforge-memory` (stdio MCP server)."""
    mcp.run()


if __name__ == "__main__":
    main()
