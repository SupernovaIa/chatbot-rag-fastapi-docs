"""Unit tests for chat prompt building."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.chat.prompts import (
    build_context_block,
    build_history_block,
    build_prompt,
    citations_from_candidates,
    system_prompt_hash,
)
from app.retrieval.models import Turn
from tests.chat.conftest import make_candidate


# ---------------------------------------------------------------------------
# build_context_block
# ---------------------------------------------------------------------------


class TestBuildContextBlock:
    def test_empty_candidates_returns_placeholder(self) -> None:
        result = build_context_block([])
        assert "No relevant documentation" in result

    def test_formats_single_candidate(self) -> None:
        c = make_candidate("h1", source="tutorial/path-params.md", section="Path Parameters")
        result = build_context_block([c])
        assert "Path Parameters" in result
        assert "tutorial/path-params.md" in result
        assert "[1]" in result

    def test_formats_multiple_candidates_with_separator(self) -> None:
        candidates = [make_candidate(f"h{i}") for i in range(3)]
        result = build_context_block(candidates)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "---" in result


# ---------------------------------------------------------------------------
# build_history_block
# ---------------------------------------------------------------------------


class TestBuildHistoryBlock:
    def test_empty_history_returns_empty_string(self) -> None:
        result = build_history_block([])
        assert result == ""

    def test_formats_turns(self) -> None:
        history = [Turn(question="What is FastAPI?", answer="A modern web framework.")]
        result = build_history_block(history)
        assert "What is FastAPI?" in result
        assert "A modern web framework." in result
        assert "Previous conversation" in result


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_returns_two_messages(self) -> None:
        messages = build_prompt("test query", [], [make_candidate("h1")])
        assert len(messages) == 2

    def test_first_message_is_system(self) -> None:
        messages = build_prompt("test query", [], [])
        assert isinstance(messages[0], SystemMessage)

    def test_second_message_is_human(self) -> None:
        messages = build_prompt("test query", [], [])
        assert isinstance(messages[1], HumanMessage)

    def test_query_in_human_message(self) -> None:
        messages = build_prompt("how do I use path params?", [], [])
        assert "how do I use path params?" in messages[1].content

    def test_system_message_stable_across_calls(self) -> None:
        msg_a = build_prompt("Q1", [], [])
        msg_b = build_prompt("Q2", [], [])
        # The system message must be identical (caching prerequisite)
        assert msg_a[0].content == msg_b[0].content

    def test_history_included_when_provided(self) -> None:
        history = [Turn(question="prior Q", answer="prior A")]
        messages = build_prompt("current Q", history, [])
        assert "prior Q" in messages[1].content
        assert "prior A" in messages[1].content

    def test_context_chunks_included(self) -> None:
        candidates = [make_candidate("h1", section="Path Parameters")]
        messages = build_prompt("Q", [], candidates)
        assert "Path Parameters" in messages[1].content


# ---------------------------------------------------------------------------
# citations_from_candidates
# ---------------------------------------------------------------------------


class TestCitationsFromCandidates:
    def test_converts_candidates_to_citations(self) -> None:
        c = make_candidate("abc123", source="docs/tutorial.md", section="Overview")
        citations = citations_from_candidates([c])
        assert len(citations) == 1
        assert citations[0].source == "docs/tutorial.md"
        assert citations[0].section == "Overview"
        assert citations[0].chunk_hash == "abc123"

    def test_empty_candidates_yields_empty_list(self) -> None:
        assert citations_from_candidates([]) == []


# ---------------------------------------------------------------------------
# system_prompt_hash (deterministic)
# ---------------------------------------------------------------------------


def test_system_prompt_hash_is_stable() -> None:
    h1 = system_prompt_hash()
    h2 = system_prompt_hash()
    assert h1 == h2
    assert len(h1) == 12  # first 12 hex chars
