"""Unit tests for PgVectorHybridSearcher with a fake engine."""

from __future__ import annotations

from app.retrieval.hybrid import PgVectorHybridSearcher, _vector_literal
from tests.retrieval.conftest import FakeEngine


def test_vector_literal_format() -> None:
    assert _vector_literal([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]"


def _searcher(rows: list[dict]) -> tuple[PgVectorHybridSearcher, FakeEngine]:
    engine = FakeEngine(rows)
    return PgVectorHybridSearcher(engine=engine, corpus_sha="sha123", rrf_k=60), engine


def test_search_maps_rows_to_candidates() -> None:
    rows = [
        {
            "chunk_hash": "a",
            "content": "alpha",
            "metadata": {"source": "a.md", "section": "A"},
            "dense_rank": 1,
            "sparse_rank": 3,
            "rrf_score": 0.5,
        },
        {
            "chunk_hash": "b",
            "content": "beta",
            "metadata": {"source": "b.md", "section": "B"},
            "dense_rank": None,
            "sparse_rank": 1,
            "rrf_score": 0.2,
        },
    ]
    searcher, _ = _searcher(rows)
    out = searcher.search([0.1] * 1536, "alpha", candidates=20, top_k=5)

    assert [c.chunk_hash for c in out] == ["a", "b"]
    assert out[0].source == "a.md"
    assert out[0].section == "A"
    assert out[0].dense_rank == 1
    assert out[1].dense_rank is None  # found only by sparse leg


def test_search_passes_corpus_and_rrf_params() -> None:
    searcher, engine = _searcher([])
    searcher.search([0.0] * 1536, "query text", candidates=20, top_k=5)

    params = engine.last_params
    assert params["corpus_sha"] == "sha123"
    assert params["k"] == 60
    assert params["query_text"] == "query text"
    assert params["candidates"] == 20
    assert params["qvec"].startswith("[") and params["qvec"].endswith("]")


def test_search_handles_missing_metadata() -> None:
    rows = [
        {
            "chunk_hash": "x",
            "content": "c",
            "metadata": None,
            "dense_rank": 1,
            "sparse_rank": None,
            "rrf_score": 0.1,
        }
    ]
    searcher, _ = _searcher(rows)
    out = searcher.search([0.0] * 1536, "q", candidates=20, top_k=5)
    assert out[0].source == ""
    assert out[0].section == ""
