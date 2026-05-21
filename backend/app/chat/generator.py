"""Streaming generation via Gemini Flash (LangChain astream).

``stream_chat`` is an async generator that yields SSE-ready event dicts:
  - {"type": "token",     "content": "..."}   — for each streamed token chunk
  - {"type": "citations", "items": [...]}      — final event with cited sources
  - {"type": "error",     "message": "..."}    — on unrecoverable errors

The generator captures ``UsageMeta`` (including ``cached_content_token_count``)
from the last streaming chunk's response_metadata and stores it on the
``StreamingSession`` object so callers can record it in traces.

Cancellation: the caller passes an ``asyncio.Event`` that is set when the
client disconnects. The generator checks it between chunks and exits cleanly,
leaving the DB turn un-saved (spec 05: abandoned turns do not advance turn_idx).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.chat.models import UsageMeta
from app.retrieval.llm import _extract_text  # shared helper

logger = logging.getLogger(__name__)


class StreamingSession:
    """Holds mutable state that the generator cannot return directly.

    After the generator is exhausted (or cancelled), inspect:
      - ``full_text``   — complete assistant response
      - ``usage``       — token usage including cached_content_token_count
      - ``cancelled``   — True if the client disconnected mid-stream
    """

    __slots__ = ("full_text", "usage", "cancelled")

    def __init__(self) -> None:
        self.full_text: str = ""
        self.usage: UsageMeta = UsageMeta()
        self.cancelled: bool = False


async def stream_chat(
    messages: list[BaseMessage],
    model: str,
    api_key: str,
    timeout: float,
    disconnect_event: asyncio.Event,
    session: StreamingSession,
) -> AsyncGenerator[dict, None]:
    """Yield SSE event dicts; write side-effects into *session*.

    Parameters
    ----------
    messages:
        The fully-built message list from ``build_prompt``.
    model:
        Gemini model ID (e.g. ``gemini-3.5-flash``).
    api_key:
        Google AI Studio API key.
    timeout:
        Request timeout in seconds for the Gemini API call.
    disconnect_event:
        Set by the router when ``request.is_disconnected()`` becomes True.
        The generator polls it between chunks and exits cleanly.
    session:
        Mutable container; the generator writes ``full_text`` and ``usage``
        here so the router can persist / trace them after the stream closes.
    """
    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.0,
        timeout=timeout,
        streaming=True,
    )

    text_parts: list[str] = []
    last_response_metadata: dict = {}

    try:
        async for chunk in llm.astream(messages):
            # Check for client disconnect before yielding each chunk.
            if disconnect_event.is_set():
                logger.debug("Client disconnected — aborting generation stream")
                session.cancelled = True
                return

            content = _extract_text(chunk.content) if chunk.content else ""
            if content:
                text_parts.append(content)
                yield {"type": "token", "content": content}

            # LangChain accumulates usage_metadata on the last chunk.
            if hasattr(chunk, "response_metadata") and chunk.response_metadata:
                last_response_metadata = chunk.response_metadata

    except asyncio.CancelledError:
        session.cancelled = True
        logger.debug("Generation task cancelled (asyncio.CancelledError)")
        return
    except Exception as exc:
        logger.warning("Generation error: %s", exc)
        yield {"type": "error", "message": str(exc)}
        session.cancelled = True
        return

    session.full_text = "".join(text_parts)
    session.usage = UsageMeta.from_response_metadata(last_response_metadata)
