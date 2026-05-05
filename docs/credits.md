# Credits

`triforge` stands on the shoulders of three brilliant open-source projects. **All credit for the algorithms, models, and code of the components belongs to their authors** — `triforge` is the integration layer.

---

## semble — Code search for AI agents

- **Project:** <https://github.com/MinishLab/semble>
- **Authors:** Thomas van Dongen ([@Pringled](https://github.com/Pringled)) and Stéphan Tulkens ([@stephantul](https://github.com/stephantul))
- **Org:** [MinishLab / minish.ai](https://minish.ai/)
- **License:** MIT

Used as: an MCP server registered globally and invoked on demand by Claude Code. We do not bundle semble; `triforge install` writes a `uvx --from "semble[mcp]" semble` entry into `~/.claude.json`. We also use MinishLab's [`model2vec`](https://github.com/MinishLab/model2vec) library directly (the `potion-base-8M` static-embedding model) for our chat-memory dense vectors.

---

## InsForge — Backend-as-a-Service for AI agents

- **Project:** <https://github.com/InsForge/InsForge>
- **Org:** **InsForge AI, Inc.**
- **License:** Apache-2.0

Used as: the **default `insforge` MCP server URL** (cloud `https://mcp.insforge.dev/mcp`) registered globally by `triforge install`. Self-hosted InsForge (Docker Compose) is also the recommended target for `triforge migrate --to=insforge`, because it ships PostgreSQL + pgvector preconfigured.

---

## HippoRAG 2 — Neurobiologically-inspired GraphRAG

- **Project:** <https://github.com/OSU-NLP-Group/HippoRAG>
- **Papers:**
    - [HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models (NeurIPS 2024)](https://arxiv.org/abs/2405.14831)
    - [From RAG to Memory: Non-Parametric Continual Learning for Large Language Models (ICML 2025)](https://arxiv.org/html/2502.14802v1)
- **Org:** **OSU NLP Group** — Ohio State University
- **License:** Apache-2.0

The triforge-memory layer is **inspired by HippoRAG 2** — same idea of LLM-driven OpenIE, NetworkX knowledge graph, and Personalized PageRank retrieval. We do not depend on the upstream `hipporag` package because it has heavy ML dependencies that don't yet support Python 3.13+. Instead, `triforge` ships its own lightweight implementation in [`memory/openie.py`](https://github.com/ilyasmukiev/triforge/blob/main/src/triforge/memory/openie.py) and [`memory/graph.py`](https://github.com/ilyasmukiev/triforge/blob/main/src/triforge/memory/graph.py) that follows HippoRAG's design with a pure-Python PPR fallback.

---

## Inspiration

The decision to use a HippoRAG-style approach for chat memory (rather than vanilla cosine RAG) was inspired by an article on Habr:

- **«Ваш RAG не умеет думать. А мой умеет»** by **rRenegat**
- Published 2026-04-24 on Habr (RUVDS company blog)
- <https://habr.com/ru/companies/ruvds/articles/1025812/>

The article walks through HippoRAG 2 and convinced us that for "remember what we discussed three sessions ago" workloads, a small KG + PPR beats a flat vector store by a wide margin in token efficiency.

---

## Other open source

- [`mcp`](https://pypi.org/project/mcp/) — Anthropic's MCP server SDK (FastMCP)
- [`bm25s`](https://github.com/xhluca/bm25s) — pure-Python BM25, way faster than rank-bm25
- [`vicinity`](https://github.com/MinishLab/vicinity) — vector store backend (also from MinishLab)
- [`networkx`](https://networkx.org/) — graph algorithms
- [`pyarrow`](https://arrow.apache.org/docs/python/) — parquet shards
- [`portalocker`](https://pypi.org/project/portalocker/) — cross-platform file locks
- [`typer`](https://typer.tiangolo.com/) + [`rich`](https://rich.readthedocs.io/) — CLI

---

## License of triforge itself

[Apache-2.0](https://github.com/ilyasmukiev/triforge/blob/main/LICENSE) — see [`NOTICE`](https://github.com/ilyasmukiev/triforge/blob/main/NOTICE) for the full third-party attribution required by the license.
