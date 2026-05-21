"""Unit tests for the multi-turn query rewriter with Gemini mocked."""

from __future__ import annotations

from app.retrieval.models import Turn
from app.retrieval.rewriter import rewrite_query
from tests.retrieval.conftest import FakeLLM


def test_empty_history_returns_query_unchanged() -> None:
    llm = FakeLLM(response="should not be used")
    out = rewrite_query("¿Qué es FastAPI?", [], llm)
    assert out == "¿Qué es FastAPI?"
    assert llm.calls == []  # LLM not invoked without history


def test_anaphora_resolved_with_history() -> None:
    history = [Turn(question="¿Qué son los path params?", answer="Variables en la URL.")]
    llm = FakeLLM(response="¿Cómo le pongo un tipo a un path parameter?")
    out = rewrite_query("¿Y cómo le pongo un tipo?", history, llm)
    assert out == "¿Cómo le pongo un tipo a un path parameter?"
    assert llm.calls  # LLM was invoked


def test_llm_failure_keeps_original_query() -> None:
    history = [Turn(question="q", answer="a")]
    llm = FakeLLM(raises=RuntimeError("boom"))
    out = rewrite_query("¿Y eso?", history, llm)
    assert out == "¿Y eso?"


def test_empty_llm_output_keeps_original() -> None:
    history = [Turn(question="q", answer="a")]
    llm = FakeLLM(response="   ")
    out = rewrite_query("¿Y eso?", history, llm)
    assert out == "¿Y eso?"


def test_sliding_window_limits_history_to_five() -> None:
    history = [Turn(question=f"q{i}", answer=f"a{i}") for i in range(8)]
    llm = FakeLLM(response="rewritten")
    rewrite_query("now", history, llm)
    prompt = llm.calls[0]
    assert "q7" in prompt and "q3" in prompt  # last 5: q3..q7
    assert "q2" not in prompt  # older turns dropped
