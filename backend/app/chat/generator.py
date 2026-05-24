"""Streaming generation via Gemini Flash (LangChain astream).

``stream_chat`` is an async generator that yields SSE-ready event dicts:
  - {"type": "token",     "content": "..."}   — for each streamed token chunk
  - {"type": "citations", "items": [...]}      — final event with cited sources
  - {"type": "error",     "message": "..."}    — on unrecoverable errors

The generator captures ``UsageMeta`` from ``chunk.usage_metadata`` (the direct
attribute on ``AIMessageChunk``), NOT from ``chunk.response_metadata``.

LangChain-Google-GenAI field mapping (confirmed against installed source):
  chunk.usage_metadata["input_tokens"]                   → prompt_token_count
  chunk.usage_metadata["output_tokens"]                  → candidates_token_count
  chunk.usage_metadata["total_tokens"]                   → total_token_count
  chunk.usage_metadata["input_token_details"]["cache_read"] → cached_content_token_count

Each chunk carries usage as a delta (not cumulative). We accumulate across all
chunks to obtain totals. ``response_metadata`` carries only model/safety/finish
info — no token counts.

Note on output_tokens: for thinking-enabled Gemini models (e.g. Gemini Flash),
``output_tokens`` includes both visible candidates tokens and internal reasoning
tokens (``output_token_details["reasoning"]``). Both are billed at the output
rate, so this is the correct value for cost estimation.

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
from app.security.safety import default_safety_settings, is_safety_block

logger = logging.getLogger(__name__)


class StreamingSession:
    """Holds mutable state that the generator cannot return directly.

    After the generator is exhausted (or cancelled), inspect:
      - ``full_text``       — complete assistant response
      - ``usage``           — token usage including cached_content_token_count
      - ``cancelled``       — True if the client disconnected mid-stream
      - ``safety_blocked``  — True if Gemini's layer-1 safety filter blocked it
      - ``finish_reason``   — the model's finish reason (for tracing)
    """

    __slots__ = ("full_text", "usage", "cancelled", "safety_blocked", "finish_reason")

    def __init__(self) -> None:
        self.full_text: str = ""
        self.usage: UsageMeta = UsageMeta()
        self.cancelled: bool = False
        self.safety_blocked: bool = False
        self.finish_reason: str | None = None


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
        # Layer 1 (spec 09): block medium-and-above harm categories. A blocked
        # generation surfaces as a SAFETY finish_reason, detected below.
        safety_settings=default_safety_settings(),
    )

    text_parts: list[str] = []

    # Accumulate usage across all chunks.
    # LangChain yields deltas per chunk; input_tokens arrive on the first chunk,
    # output_tokens are distributed across chunks as generation proceeds.
    acc_input: int = 0
    acc_output: int = 0
    acc_total: int = 0
    acc_cache_read: int = 0

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

            # Capture the finish reason (layer 1). LangChain surfaces it in
            # response_metadata; a SAFETY/PROHIBITED_CONTENT value means Gemini
            # blocked the generation rather than completing it normally.
            rm: dict | None = getattr(chunk, "response_metadata", None)
            if rm and rm.get("finish_reason"):
                session.finish_reason = str(rm["finish_reason"])

            # Accumulate token usage from chunk.usage_metadata (direct attribute).
            # response_metadata does NOT contain token counts; usage_metadata does.
            um: dict | None = getattr(chunk, "usage_metadata", None)
            if um:
                acc_input += um.get("input_tokens", 0)
                acc_output += um.get("output_tokens", 0)
                acc_total += um.get("total_tokens", 0)
                acc_cache_read += (um.get("input_token_details") or {}).get("cache_read", 0)

    except asyncio.CancelledError:
        session.cancelled = True
        logger.debug("Generation task cancelled (asyncio.CancelledError)")
        return
    except Exception as exc:
        logger.warning("Generation error: %s", exc)
        yield {"type": "error", "message": str(exc)}
        session.cancelled = True
        return

    # Layer 1: if Gemini blocked for safety, flag it so the router returns a
    # safe response and logs the incident instead of persisting empty output.
    if is_safety_block(session.finish_reason):
        session.safety_blocked = True
        logger.info("Generation blocked by Gemini safety (finish_reason=%s)",
                    session.finish_reason)

    session.full_text = "".join(text_parts)
    session.usage = UsageMeta(
        prompt_token_count=acc_input,
        candidates_token_count=acc_output,
        total_token_count=acc_total,
        cached_content_token_count=acc_cache_read,
    )
    logger.debug(
        "Stream complete: prompt=%d output=%d total=%d cached=%d",
        acc_input, acc_output, acc_total, acc_cache_read,
    )
