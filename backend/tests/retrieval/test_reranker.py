"""Unit tests for the RankGPT reranker with Gemini mocked."""

from __future__ import annotations

import json

from app.retrieval.llm import GeminiChatAdapter, _extract_text
from app.retrieval.reranker import rerank, rerank_with_stats
from tests.retrieval.conftest import FakeLLM, make_candidate


def test_extract_text_plain_string() -> None:
    assert _extract_text("hello") == "hello"


def test_chat_adapter_propagates_timeout_to_client() -> None:
    # The request timeout must live on the underlying client, not be ignored
    # as a per-call config (which is what silently broke spec 03's 5s rule).
    adapter = GeminiChatAdapter(api_key="x", model="gemini-3.5-flash", timeout=5.0)
    assert adapter._llm.timeout == 5.0


def test_extract_text_thinking_blocks() -> None:
    # Gemini 3.x returns a list of content blocks; only 'text' blocks count.
    content = [
        {"type": "thinking", "thinking": "let me reason"},
        {"type": "text", "text": '{"ranking": ["a"]}', "extras": {"signature": "xx"}},
    ]
    assert _extract_text(content) == '{"ranking": ["a"]}'


def _candidates():
    return [make_candidate("c1"), make_candidate("c2"), make_candidate("c3")]


def test_valid_json_reorders_candidates() -> None:
    llm = FakeLLM(response=json.dumps({"ranking": ["c3", "c1", "c2"]}))
    out = rerank("q", _candidates(), llm, top_k=3)
    assert [c.chunk_hash for c in out] == ["c3", "c1", "c2"]
    assert [c.rerank_position for c in out] == [1, 2, 3]


def test_top_k_truncates() -> None:
    llm = FakeLLM(response=json.dumps({"ranking": ["c3", "c1", "c2"]}))
    out = rerank("q", _candidates(), llm, top_k=2)
    assert [c.chunk_hash for c in out] == ["c3", "c1"]


def test_garbage_output_falls_back_to_original_order() -> None:
    llm = FakeLLM(response="I cannot help with that.")
    out, fallback = rerank_with_stats("q", _candidates(), llm, top_k=3)
    assert [c.chunk_hash for c in out] == ["c1", "c2", "c3"]
    assert fallback is True


def test_llm_exception_falls_back() -> None:
    llm = FakeLLM(raises=TimeoutError("too slow"))
    out, fallback = rerank_with_stats("q", _candidates(), llm, top_k=3)
    assert [c.chunk_hash for c in out] == ["c1", "c2", "c3"]
    assert fallback is True


def test_invented_ids_are_dropped() -> None:
    llm = FakeLLM(response=json.dumps({"ranking": ["c2", "zzz", "c1"]}))
    out = rerank("q", _candidates(), llm, top_k=3)
    # c3 (omitted by model) is appended after the known ranked ids.
    assert [c.chunk_hash for c in out] == ["c2", "c1", "c3"]


def test_json_embedded_in_prose_is_parsed() -> None:
    llm = FakeLLM(response='Sure! {"ranking": ["c2", "c3", "c1"]} done.')
    out = rerank("q", _candidates(), llm, top_k=3)
    assert [c.chunk_hash for c in out] == ["c2", "c3", "c1"]


def test_empty_candidates_returns_empty() -> None:
    out, fallback = rerank_with_stats("q", [], FakeLLM(), top_k=5)
    assert out == []
    assert fallback is False
