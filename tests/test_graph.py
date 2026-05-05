from __future__ import annotations

from pathlib import Path

from triforge.memory.graph import (
    add_triplets,
    graph_search,
    index_chunks_into_graph,
    load_graph,
    save_graph,
)
from triforge.memory.openie import Triplet


def test_load_empty_graph(tmp_home: Path) -> None:
    g = load_graph("empty-hash")
    assert g.number_of_nodes() == 0


def test_add_triplets_creates_nodes_and_edges(tmp_home: Path) -> None:
    g = load_graph("h1")
    triplets = [
        Triplet("Flask", "uses", "sessions"),
        Triplet("sessions", "signed_with", "SECRET_KEY"),
    ]
    n = add_triplets(g, "chunk-1", triplets)
    assert n == 2
    assert g.number_of_nodes() == 3
    assert g.number_of_edges() == 2


def test_save_load_roundtrip(tmp_home: Path) -> None:
    g = load_graph("h2")
    add_triplets(g, "c1", [Triplet("X", "rel", "Y")])
    save_graph("h2", g)
    g2 = load_graph("h2")
    assert g2.number_of_nodes() == 2
    assert g2.has_edge("x", "y")


def test_index_chunks_into_graph(tmp_home: Path) -> None:
    chunks = [
        ("c1", [Triplet("Database", "stores", "users")]),
        ("c2", [
            Triplet("users", "have", "passwords"),
            Triplet("passwords", "hashed_with", "bcrypt"),
        ]),
    ]
    n_chunks, n_triplets = index_chunks_into_graph("h3", chunks)
    assert n_chunks == 2
    assert n_triplets == 3


def test_graph_search_empty_returns_empty(tmp_home: Path) -> None:
    assert graph_search("never-indexed", "anything") == []


def test_graph_search_finds_relevant_chunks(tmp_home: Path) -> None:
    chunks = [
        ("c-flask", [
            Triplet("Flask", "uses", "sessions"),
            Triplet("sessions", "signed_with", "SECRET_KEY"),
        ]),
        ("c-pandas", [
            Triplet("pandas", "reads", "csv"),
            Triplet("csv", "encoded_as", "utf-8"),
        ]),
    ]
    index_chunks_into_graph("hgs", chunks)
    hits = graph_search("hgs", "flask sessions", top_k=5)
    assert hits, "expected at least one chunk hit"
    assert hits[0].chunk_id == "c-flask"


def test_graph_search_no_matching_seed(tmp_home: Path) -> None:
    chunks = [("c1", [Triplet("Flask", "uses", "sessions")])]
    index_chunks_into_graph("hns", chunks)
    assert graph_search("hns", "completely unrelated topic") == []
