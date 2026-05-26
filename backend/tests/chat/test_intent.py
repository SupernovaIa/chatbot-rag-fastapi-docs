"""Tests for retrieval gating — the Flash intent classifier (spec 14, ADR-013)."""

from __future__ import annotations

import pytest

from app.chat.intent import IntentGate, _parse_verdict
from app.retrieval.models import Turn


class _FakeLLM:
    """Stub ChatLLMPort returning a canned string (or raising)."""

    def __init__(self, response: str | None = None, raises: bool = False) -> None:
        self._response = response
        self._raises = raises
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self._raises:
            raise RuntimeError("boom")
        return self._response or ""


class TestParseVerdict:
    def test_parses_plain_json_true(self) -> None:
        v = _parse_verdict('{"needs_retrieval": true, "reason": "technical"}')
        assert v.needs_retrieval
        assert v.reason == "technical"
        assert not v.failed_open

    def test_parses_plain_json_false(self) -> None:
        v = _parse_verdict('{"needs_retrieval": false, "reason": "greeting"}')
        assert not v.needs_retrieval
        assert not v.failed_open

    def test_parses_json_in_code_fence(self) -> None:
        raw = '```json\n{"needs_retrieval": false, "reason": "thanks"}\n```'
        v = _parse_verdict(raw)
        assert not v.needs_retrieval

    def test_parses_json_with_surrounding_prose(self) -> None:
        raw = 'Sure: {"needs_retrieval": true} — that is my answer.'
        v = _parse_verdict(raw)
        assert v.needs_retrieval

    @pytest.mark.parametrize("raw", ["not json at all", '{"foo": "bar"}', ""])
    def test_unparseable_or_missing_field_fails_open_to_retrieve(self, raw: str) -> None:
        v = _parse_verdict(raw)
        assert v.needs_retrieval  # fail-open is toward RETRIEVE
        assert v.failed_open


class TestIntentGate:
    def test_greeting_skips_retrieval(self) -> None:
        g = IntentGate(_FakeLLM('{"needs_retrieval": false, "reason": "greeting"}'))
        v = g.classify("hola")
        assert not v.needs_retrieval

    def test_technical_question_retrieves(self) -> None:
        g = IntentGate(_FakeLLM('{"needs_retrieval": true, "reason": "technical"}'))
        v = g.classify("how do I define an optional query parameter?")
        assert v.needs_retrieval

    def test_query_and_history_injected_into_prompt(self) -> None:
        llm = _FakeLLM('{"needs_retrieval": true}')
        history = [Turn(question="PREV_Q", answer="PREV_A")]
        IntentGate(llm).classify("MY_UNIQUE_QUERY", history)
        assert "MY_UNIQUE_QUERY" in llm.calls[0]
        assert "PREV_Q" in llm.calls[0]
        assert "PREV_A" in llm.calls[0]

    def test_empty_history_renders_placeholder(self) -> None:
        llm = _FakeLLM('{"needs_retrieval": true}')
        IntentGate(llm).classify("anything", [])
        assert "no previous turns" in llm.calls[0]

    def test_llm_error_fails_open_to_retrieve(self) -> None:
        g = IntentGate(_FakeLLM(raises=True))
        v = g.classify("anything")
        assert v.needs_retrieval
        assert v.failed_open
