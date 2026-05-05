"""Hybrid retrieval: dense + BM25 + Reciprocal Rank Fusion."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

import bm25s
import numpy as np

from triforge._embedder import embed
from triforge.memory.store import VectorRecord, load_all_vectors

Mode = Literal["hybrid", "dense", "bm25"]


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    role: str
    session_id: str
    ts: str
    score: float
    source: Literal["dense", "bm25", "hybrid"]


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


def _rrf(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    out: dict[int, float] = {}
    for ranks in rank_lists:
        for r, idx in enumerate(ranks):
            out[idx] = out.get(idx, 0.0) + 1.0 / (k + r + 1)
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
        return [
            SearchHit(
                chunk_id=recs[i].chunk_id, text=recs[i].text, role=recs[i].role,
                session_id=recs[i].session_id, ts=recs[i].ts,
                score=float(scores[i]), source="dense",
            )
            for i in order
        ]

    if mode == "bm25":
        scores = _bm25_scores(query, recs)
        order = list(np.argsort(-scores)[:top_k])
        return [
            SearchHit(
                chunk_id=recs[i].chunk_id, text=recs[i].text, role=recs[i].role,
                session_id=recs[i].session_id, ts=recs[i].ts,
                score=float(scores[i]), source="bm25",
            )
            for i in order
        ]

    # hybrid (default)
    dense = _dense_scores(query, recs)
    bm = _bm25_scores(query, recs)
    d_ranks = list(np.argsort(-dense)[:top_k])
    b_ranks = list(np.argsort(-bm)[:top_k])
    rrf = _rrf([list(map(int, d_ranks)), list(map(int, b_ranks))])
    order = sorted(rrf.keys(), key=lambda i: -rrf[i])[:top_k]
    return [
        SearchHit(
            chunk_id=recs[i].chunk_id, text=recs[i].text, role=recs[i].role,
            session_id=recs[i].session_id, ts=recs[i].ts,
            score=float(rrf[i]), source="hybrid",
        )
        for i in order
    ]
