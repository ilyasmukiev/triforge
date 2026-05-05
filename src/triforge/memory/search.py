"""Hybrid retrieval: dense + BM25 + graph PPR + Reciprocal Rank Fusion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import bm25s
import numpy as np

from triforge._embedder import embed
from triforge.memory.graph import graph_search
from triforge.memory.store import VectorRecord, load_all_vectors

Mode = Literal["hybrid", "dense", "bm25", "graph"]
HitSource = Literal["dense", "bm25", "graph", "hybrid"]


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    role: str
    session_id: str
    ts: str
    score: float
    source: HitSource


def _dense_scores(query: str, recs: list[VectorRecord]) -> np.ndarray:
    if not recs:
        return np.zeros(0, dtype=np.float32)
    q = embed(query)
    M = np.stack([r.vector for r in recs])
    qn = q / (np.linalg.norm(q) + 1e-9)
    Mn = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    return (Mn @ qn).astype(np.float32)


def _bm25_scores(query: str, recs: list[VectorRecord]) -> np.ndarray:
    if not recs:
        return np.zeros(0, dtype=np.float32)
    corpus_tokens = bm25s.tokenize([r.text for r in recs])
    bm = bm25s.BM25()
    bm.index(corpus_tokens)
    q_tokens = bm25s.tokenize([query])
    idx_arr, sc_arr = bm.retrieve(q_tokens, k=len(recs))
    flat = np.zeros(len(recs), dtype=np.float32)
    for j, s in zip(idx_arr[0], sc_arr[0]):
        flat[int(j)] = float(s)
    return flat


def _graph_index_ranks(
    project_hash: str, query: str, recs: list[VectorRecord], top_k: int
) -> list[int]:
    """Map graph PPR results (chunk_ids) to indices into ``recs``."""
    by_id = {r.chunk_id: i for i, r in enumerate(recs)}
    hits = graph_search(project_hash, query, top_k=top_k * 2)
    out: list[int] = []
    for h in hits:
        if h.chunk_id in by_id:
            out.append(by_id[h.chunk_id])
        if len(out) >= top_k:
            break
    return out


def _rrf(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    out: dict[int, float] = {}
    for ranks in rank_lists:
        for r, idx in enumerate(ranks):
            out[idx] = out.get(idx, 0.0) + 1.0 / (k + r + 1)
    return out


def _hits_from_order(
    recs: list[VectorRecord],
    order: list[int],
    scores: list[float],
    source: HitSource,
) -> list[SearchHit]:
    out: list[SearchHit] = []
    for k_, i in enumerate(order):
        rec = recs[i]
        out.append(
            SearchHit(
                chunk_id=rec.chunk_id,
                text=rec.text,
                role=rec.role,
                session_id=rec.session_id,
                ts=rec.ts,
                score=float(scores[k_]),
                source=source,
            )
        )
    return out


def search(
    project_hash: str,
    query: str,
    top_k: int = 5,
    mode: Mode = "hybrid",
) -> list[SearchHit]:
    recs = load_all_vectors(project_hash)
    if not recs:
        return []

    if mode == "dense":
        scores = _dense_scores(query, recs)
        order = list(np.argsort(-scores)[:top_k])
        return _hits_from_order(recs, list(map(int, order)), [float(scores[i]) for i in order], "dense")

    if mode == "bm25":
        scores = _bm25_scores(query, recs)
        order = list(np.argsort(-scores)[:top_k])
        return _hits_from_order(recs, list(map(int, order)), [float(scores[i]) for i in order], "bm25")

    if mode == "graph":
        order = _graph_index_ranks(project_hash, query, recs, top_k)
        return _hits_from_order(recs, order, [1.0 / (k + 1) for k in range(len(order))], "graph")

    # hybrid (default): dense + BM25 + (graph if available) → RRF
    dense_order = list(map(int, np.argsort(-_dense_scores(query, recs))[:top_k]))
    bm_order = list(map(int, np.argsort(-_bm25_scores(query, recs))[:top_k]))
    graph_order = _graph_index_ranks(project_hash, query, recs, top_k)

    rank_lists = [dense_order, bm_order]
    if graph_order:
        rank_lists.append(graph_order)
    rrf = _rrf(rank_lists)
    order = sorted(rrf.keys(), key=lambda i: -rrf[i])[:top_k]
    return _hits_from_order(recs, order, [float(rrf[i]) for i in order], "hybrid")
