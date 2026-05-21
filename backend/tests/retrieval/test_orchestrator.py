"""End-to-end orchestrator test wiring all fakes (no network, no DB)."""

from __future__ import annotations

import json

from app.retrieval.models import Turn
from app.retrieval.orchestrator import retrieve
from tests.retrieval.conftest import (
    FakeEmbeddings,
    FakeLLM,
    FakeSearcher,
    make_candidate,
)


def test_pipeline_returns_reranked_top_k() -> None:
    candidates = [make_candidate(f"c{i}") for i in range(20)]
    searcher = FakeSearcher(candidates)
    embeddings = FakeEmbeddings()
    ranking = {"ranking": [f"c{i}" for i in reversed(range(20))]}
    rewrite_llm = FakeLLM(response="unused")  # no history → not called
    rerank_llm = FakeLLM(response=json.dumps(ranking))

    result = retrieve(
        query="¿Qué es un path parameter?",
        embeddings=embeddings,
        searcher=searcher,
        rewrite_llm=rewrite_llm,
        rerank_llm=rerank_llm,
        history=[],
        candidates=20,
        top_k=5,
    )

    assert len(result.candidates) == 5
    assert result.candidates[0].chunk_hash == "c19"  # reranked first
    assert result.candidates[0].rerank_position == 1
    assert result.original_query == result.rewritten_query  # no history
    assert result.rerank_fallback_used is False
    assert rewrite_llm.calls == []  # rewrite LLM not invoked without history


def test_pipeline_uses_rewritten_query_for_search() -> None:
    candidates = [make_candidate("c0")]
    searcher = FakeSearcher(candidates)
    embeddings = FakeEmbeddings()
    rewrite_llm = FakeLLM(response="standalone question")
    rerank_llm = FakeLLM(response=json.dumps({"ranking": ["c0"]}))
    history = [Turn(question="q", answer="a")]

    retrieve(
        query="¿y eso?",
        embeddings=embeddings,
        searcher=searcher,
        rewrite_llm=rewrite_llm,
        rerank_llm=rerank_llm,
        history=history,
        candidates=20,
        top_k=5,
    )
    # The rewritten query is what gets embedded and searched.
    assert embeddings.last_text == "standalone question"
    assert searcher.last_query_text == "standalone question"


def test_pipeline_falls_back_on_bad_rerank() -> None:
    candidates = [make_candidate(f"c{i}") for i in range(3)]
    searcher = FakeSearcher(candidates)
    embeddings = FakeEmbeddings()
    rewrite_llm = FakeLLM(response="unused")
    rerank_llm = FakeLLM(response="garbage not json")

    result = retrieve(
        query="q",
        embeddings=embeddings,
        searcher=searcher,
        rewrite_llm=rewrite_llm,
        rerank_llm=rerank_llm,
        history=[],
        candidates=20,
        top_k=3,
    )
    assert [c.chunk_hash for c in result.candidates] == ["c0", "c1", "c2"]
    assert result.rerank_fallback_used is True


def test_pipeline_falls_back_on_rerank_timeout() -> None:
    # A slow rerank client raises (its timeout fires) → hybrid order is kept.
    candidates = [make_candidate(f"c{i}") for i in range(3)]
    searcher = FakeSearcher(candidates)
    embeddings = FakeEmbeddings()
    rewrite_llm = FakeLLM(response="unused")
    rerank_llm = FakeLLM(raises=TimeoutError("deadline exceeded"))

    result = retrieve(
        query="q",
        embeddings=embeddings,
        searcher=searcher,
        rewrite_llm=rewrite_llm,
        rerank_llm=rerank_llm,
        history=[],
        candidates=20,
        top_k=3,
    )
    assert [c.chunk_hash for c in result.candidates] == ["c0", "c1", "c2"]
    assert result.rerank_fallback_used is True
