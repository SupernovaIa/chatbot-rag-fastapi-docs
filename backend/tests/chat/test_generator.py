"""Unit tests for the streaming generator."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.chat.generator import StreamingSession, stream_chat
from app.chat.models import UsageMeta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(text: str, meta: dict | None = None):
    chunk = MagicMock()
    chunk.content = text
    chunk.response_metadata = meta or {}
    return chunk


async def _drain(gen) -> list[dict]:
    events: list[dict] = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# UsageMeta
# ---------------------------------------------------------------------------


class TestUsageMeta:
    def test_from_empty_metadata(self) -> None:
        u = UsageMeta.from_response_metadata({})
        assert u.prompt_token_count == 0
        assert u.cached_content_token_count == 0

    def test_from_populated_metadata(self) -> None:
        meta = {
            "usage_metadata": {
                "prompt_token_count": 200,
                "cached_content_token_count": 150,
                "candidates_token_count": 80,
                "total_token_count": 280,
            }
        }
        u = UsageMeta.from_response_metadata(meta)
        assert u.prompt_token_count == 200
        assert u.cached_content_token_count == 150
        assert u.candidates_token_count == 80

    def test_from_none_metadata(self) -> None:
        u = UsageMeta.from_response_metadata(None)
        assert u.total_token_count == 0


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

    async def test_captures_usage_from_last_chunk(self) -> None:
        meta = {"usage_metadata": {"cached_content_token_count": 42, "prompt_token_count": 300}}
        chunks = [_make_chunk("tok", meta)]
        _, session = await self._run(chunks)
        assert session.usage.cached_content_token_count == 42
        assert session.usage.prompt_token_count == 300

    async def test_disconnect_cancels_stream(self) -> None:
        # Disconnect after first chunk
        chunks = [_make_chunk("A"), _make_chunk("B"), _make_chunk("C")]
        events, session = await self._run(chunks, disconnect_after=1)
        # Some events may have been yielded before disconnect
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
        # Empty string content → no token event
        chunks = [_make_chunk(""), _make_chunk("real")]
        events, _ = await self._run(chunks)
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) == 1
        assert token_events[0]["content"] == "real"
