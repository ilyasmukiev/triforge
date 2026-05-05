"""Per-project knowledge graph (NetworkX) with Personalized PageRank retrieval.

Inspired by HippoRAG 2 (OSU NLP Group, Apache-2.0). Stored as a single
``kg.pkl`` next to ``vectors/``. Nodes are entity strings; edges carry
``relation`` labels and a list of ``chunk_ids`` they came from. Search
seeds the PPR with entities that match the query (substring) and ranks
chunks by accumulated PPR mass on the entities they touch.
"""
from __future__ import annotations

import pickle
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from triforge._paths import project_dir
from triforge.memory.openie import Triplet


def _kg_path(project_hash: str) -> Path:
    return project_dir(project_hash) / "kg.pkl"


def load_graph(project_hash: str) -> nx.MultiDiGraph:
    p = _kg_path(project_hash)
    if not p.exists():
        return nx.MultiDiGraph()
    with p.open("rb") as f:
        return pickle.load(f)


def save_graph(project_hash: str, g: nx.MultiDiGraph) -> None:
    p = _kg_path(project_hash)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        pickle.dump(g, f)


def add_triplets(g: nx.MultiDiGraph, chunk_id: str, triplets: Iterable[Triplet]) -> int:
    """Add triplets to ``g`` (in place); annotate edges with originating chunk_id."""
    n = 0
    for t in triplets:
        s = t.subject.lower()
        o = t.object.lower()
        g.add_node(s, label=t.subject)
        g.add_node(o, label=t.object)
        existing = g.get_edge_data(s, o, default={})
        # try to merge into an edge with the same relation
        merged = False
        for _, ed in existing.items():
            if ed.get("relation") == t.relation:
                chunks = ed.setdefault("chunks", [])
                if chunk_id not in chunks:
                    chunks.append(chunk_id)
                merged = True
                break
        if not merged:
            g.add_edge(s, o, relation=t.relation, chunks=[chunk_id])
        n += 1
    return n


def index_chunks_into_graph(
    project_hash: str,
    chunks: list[tuple[str, list[Triplet]]],
) -> tuple[int, int]:
    """Persist new triplets for the supplied chunks; returns (n_chunks, n_triplets)."""
    if not chunks:
        return (0, 0)
    g = load_graph(project_hash)
    total = 0
    for chunk_id, trs in chunks:
        total += add_triplets(g, chunk_id, trs)
    save_graph(project_hash, g)
    return (len(chunks), total)


@dataclass
class GraphHit:
    chunk_id: str
    score: float


def _pure_python_ppr(
    g: nx.DiGraph,
    personalization: dict[str, float],
    *,
    alpha: float = 0.5,
    iterations: int = 30,
) -> dict[str, float]:
    """Tiny pure-Python Personalized PageRank — no scipy needed.

    Power iteration with damping ``alpha``; ``personalization`` is the
    teleport distribution. Adequate for the small per-project graphs
    triforge produces.
    """
    nodes = list(g.nodes)
    if not nodes:
        return {}
    n = len(nodes)
    # Out-edge counts (with weight)
    out_w: dict[str, float] = {}
    for u, _v, data in g.edges(data=True):
        out_w[u] = out_w.get(u, 0.0) + float(data.get("weight", 1))
    # Initial uniform; teleport drives early bias toward personalization
    rank = dict.fromkeys(nodes, 1.0 / n)
    pers_total = sum(personalization.values()) or 1.0
    pers_norm = {k: v / pers_total for k, v in personalization.items()}
    for _ in range(iterations):
        new_rank = {n_: (1.0 - alpha) * pers_norm.get(n_, 0.0) for n_ in nodes}
        for u, v, data in g.edges(data=True):
            if out_w.get(u, 0.0) <= 0:
                continue
            w = float(data.get("weight", 1)) / out_w[u]
            new_rank[v] = new_rank.get(v, 0.0) + alpha * rank[u] * w
        rank = new_rank
    return rank


def _seed_nodes(g: nx.MultiDiGraph, query: str) -> list[str]:
    """Return graph nodes whose label contains any non-trivial query token."""
    q_lower = query.lower()
    tokens = [t for t in q_lower.split() if len(t) >= 3]
    if not tokens:
        return []
    seeds: set[str] = set()
    for n in g.nodes:
        nl = n.lower()
        if any(t in nl for t in tokens):
            seeds.add(n)
    return sorted(seeds)


def graph_search(
    project_hash: str,
    query: str,
    *,
    top_k: int = 10,
    alpha: float = 0.5,
) -> list[GraphHit]:
    """Personalized PageRank from query-matching seeds; rank chunks by PPR mass.

    Returns ``[]`` if the graph is empty or no seed nodes match.
    """
    g = load_graph(project_hash)
    if g.number_of_nodes() == 0:
        return []
    seeds = _seed_nodes(g, query)
    if not seeds:
        return []

    personalization = {n: (1.0 / len(seeds) if n in seeds else 0.0) for n in g.nodes}
    # nx.pagerank requires a simple DiGraph view of the multigraph
    simple = nx.DiGraph()
    simple.add_nodes_from(g.nodes(data=True))
    for u, v, _data in g.edges(data=True):
        if simple.has_edge(u, v):
            simple[u][v]["weight"] = simple[u][v].get("weight", 0) + 1
        else:
            simple.add_edge(u, v, weight=1)
    try:
        ranks = nx.pagerank(
            simple, alpha=alpha, personalization=personalization, max_iter=100
        )
    except (nx.PowerIterationFailedConvergence, ImportError, ModuleNotFoundError):
        # scipy missing or convergence failed → simple pure-Python PPR
        ranks = _pure_python_ppr(simple, personalization, alpha=alpha, iterations=30)

    chunk_scores: dict[str, float] = {}
    for u, v, data in g.edges(data=True):
        share = (ranks.get(u, 0.0) + ranks.get(v, 0.0)) / 2.0
        for cid in data.get("chunks", []):
            chunk_scores[cid] = chunk_scores.get(cid, 0.0) + share

    ordered = sorted(chunk_scores.items(), key=lambda kv: -kv[1])[:top_k]
    return [GraphHit(chunk_id=cid, score=float(score)) for cid, score in ordered]
