"""Unit tests for the streaming generator.

Key fixture change (block F token-fix): ``AIMessageChunk`` exposes usage on
``chunk.usage_metadata`` (a dict with LangChain field names), NOT inside
``chunk.response_metadata["usage_metadata"]``.  Mocks must set the attribute
directly on the chunk object, not nested inside response_metadata.

LangChain field names:
  input_tokens                        → UsageMeta.prompt_token_count
  output_tokens                       → UsageMeta.candidates_token_count
  total_tokens                        → UsageMeta.total_token_count
  input_token_details["cache_read"]   → UsageMeta.cached_content_token_count
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.chat.generator import StreamingSession, stream_chat
from app.chat.models import UsageMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    text: str,
    usage: dict | None = None,
    finish_reason: str | None = None,
):
    """Create a mock AIMessageChunk.

    ``usage`` is set as the direct ``usage_metadata`` attribute on the chunk
    (LangChain field names: input_tokens, output_tokens, total_tokens,
    input_token_details).  ``response_metadata`` carries only safety/finish info.
    """
    chunk = MagicMock()
    chunk.content = text
    chunk.usage_metadata = usage  # None → no usage on this chunk
    chunk.response_metadata = {"finish_reason": finish_reason} if finish_reason else {}
    return chunk


async def _drain(gen) -> list[dict]:
    events: list[dict] = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# UsageMeta — constructor and field semantics
# ---------------------------------------------------------------------------


class TestUsageMeta:
    def test_defaults_zero(self) -> None:
        u = UsageMeta()
        assert u.prompt_token_count == 0
        assert u.candidates_token_count == 0
        assert u.total_token_count == 0
        assert u.cached_content_token_count == 0

    def test_explicit_fields(self) -> None:
        u = UsageMeta(
            prompt_token_count=200,
            candidates_token_count=80,
            total_token_count=280,
            cached_content_token_count=150,
        )
        assert u.prompt_token_count == 200
        assert u.candidates_token_count == 80
        assert u.total_token_count == 280
        assert u.cached_content_token_count == 150


# ---------------------------------------------------------------------------
# stream_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreamChat:
    async def _run(self, chunks, disconnect_after: int = 999):
        disconnect = asyncio.Event()
        session = StreamingSession()

        async def _fake_astream(_):
            for i, chunk in enumerate(chunks):
                if i >= disconnect_after:
                    disconnect.set()
                yield chunk

        with patch(
            "app.chat.generator.ChatGoogleGenerativeAI"
        ) as MockLLM:
            instance = MagicMock()
            instance.astream = _fake_astream
            MockLLM.return_value = instance

            events = await _drain(
                stream_chat(
                    messages=[],
                    model="gemini-3.5-flash",
                    api_key="fake-key",
                    timeout=10.0,
                    disconnect_event=disconnect,
                    session=session,
                )
            )
        return events, session

    async def test_yields_token_events(self) -> None:
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        events, session = await self._run(chunks)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) == 2
        assert token_events[0]["content"] == "Hello"
        assert token_events[1]["content"] == " world"

    async def test_full_text_accumulated(self) -> None:
        chunks = [_make_chunk("Hello"), _make_chunk(" world")]
        _, session = await self._run(chunks)
        assert session.full_text == "Hello world"

    async def test_captures_usage_from_chunk_usage_metadata(self) -> None:
        """Usage must be read from chunk.usage_metadata (LangChain field names)."""
        # First chunk carries prompt tokens (input_tokens) and first output delta.
        # Subsequent chunks carry only output deltas.
        chunks = [
            _make_chunk(
                "tok1",
                usage={
                    "input_tokens": 300,
                    "output_tokens": 10,
                    "total_tokens": 310,
                    "input_token_details": {"cache_read": 42},
                },
            ),
            _make_chunk(
                "tok2",
                usage={
                    "input_tokens": 0,
                    "output_tokens": 5,
                    "total_tokens": 5,
                    "input_token_details": {"cache_read": 0},
                },
            ),
        ]
        _, session = await self._run(chunks)
        # Accumulated across both chunks
        assert session.usage.prompt_token_count == 300
        assert session.usage.candidates_token_count == 15   # 10 + 5
        assert session.usage.total_token_count == 315        # 310 + 5
        assert session.usage.cached_content_token_count == 42

    async def test_usage_none_chunks_handled(self) -> None:
        """Chunks with usage_metadata=None must not crash and contribute 0."""
        chunks = [_make_chunk("A", usage=None), _make_chunk("B", usage=None)]
        _, session = await self._run(chunks)
        assert session.usage.prompt_token_count == 0
        assert session.usage.candidates_token_count == 0

    async def test_usage_missing_input_token_details(self) -> None:
        """input_token_details absent → cache_read treated as 0."""
        chunks = [
            _make_chunk("tok", usage={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}),
        ]
        _, session = await self._run(chunks)
        assert session.usage.prompt_token_count == 100
        assert session.usage.cached_content_token_count == 0

    async def test_disconnect_cancels_stream(self) -> None:
        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        events, session = await self._run(chunks, disconnect_after=1)
        assert session.cancelled is True

    async def test_error_yields_error_event(self) -> None:
        disconnect = asyncio.Event()
        session = StreamingSession()

        async def _failing_astream(_):
            yield _make_chunk("partial")
            raise RuntimeError("LLM error")

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            instance = MagicMock()
            instance.astream = _failing_astream
            MockLLM.return_value = instance

            events = await _drain(
                stream_chat(
                    messages=[],
                    model="gemini-3.5-flash",
                    api_key="fake-key",
                    timeout=10.0,
                    disconnect_event=disconnect,
                    session=session,
                )
            )

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "LLM error" in error_events[0]["message"]
        assert session.cancelled is True

    async def test_empty_content_chunks_not_yielded(self) -> None:
        chunks = [_make_chunk(""), _make_chunk("real")]
        events, _ = await self._run(chunks)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) == 1
        assert token_events[0]["content"] == "real"
