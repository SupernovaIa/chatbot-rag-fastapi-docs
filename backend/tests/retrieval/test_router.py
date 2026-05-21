"""Route test for POST /retrieve with dependencies overridden (no DB, no LLM)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.retrieval.router import (
    get_embeddings,
    get_rerank_llm,
    get_rewrite_llm,
    get_searcher,
)
from tests.retrieval.conftest import (
    FakeEmbeddings,
    FakeLLM,
    FakeSearcher,
    make_candidate,
)


def _client(candidates, llm_response):
    app.dependency_overrides[get_searcher] = lambda: FakeSearcher(candidates)
    app.dependency_overrides[get_embeddings] = lambda: FakeEmbeddings()
    app.dependency_overrides[get_rewrite_llm] = lambda: FakeLLM(response="unused")
    app.dependency_overrides[get_rerank_llm] = lambda: FakeLLM(response=llm_response)
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_retrieve_returns_top_5_with_scores() -> None:
    candidates = [make_candidate(f"c{i}", rrf=1.0 / (i + 1)) for i in range(20)]
    ranking = json.dumps({"ranking": [f"c{i}" for i in range(20)]})
    client = _client(candidates, ranking)

    resp = client.post("/retrieve", json={"query": "¿Qué es un path parameter?"})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["candidates"]) == 5
    first = body["candidates"][0]
    assert first["chunk_hash"] == "c0"
    assert first["rerank_position"] == 1
    assert "rrf_score" in first and "source" in first and "section" in first
    assert body["original_query"] == body["rewritten_query"]  # no history
    assert body["rerank_fallback_used"] is False


def test_retrieve_respects_top_k_override() -> None:
    candidates = [make_candidate(f"c{i}") for i in range(20)]
    ranking = json.dumps({"ranking": [f"c{i}" for i in range(20)]})
    client = _client(candidates, ranking)

    resp = client.post("/retrieve", json={"query": "q", "top_k": 3})
    assert resp.status_code == 200
    assert len(resp.json()["candidates"]) == 3


def test_retrieve_rejects_empty_query() -> None:
    client = _client([make_candidate("c0")], json.dumps({"ranking": ["c0"]}))
    resp = client.post("/retrieve", json={"query": ""})
    assert resp.status_code == 422
