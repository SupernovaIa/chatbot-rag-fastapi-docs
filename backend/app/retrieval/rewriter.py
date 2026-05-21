"""Multi-turn query rewriting (standalone question).

Spec 04 / ADR-005. Uses the last N=5 turns of history to resolve anaphora in
the current question. If history is empty or the LLM fails, the original query
is returned unchanged (with a warning).
"""

from __future__ import annotations

import logging

from app.observability.tracing import set_span_attributes, traced
from app.retrieval.models import Turn
from app.retrieval.ports import ChatLLMPort
from app.retrieval.prompts import load_prompt, render

logger = logging.getLogger(__name__)

_WINDOW = 5  # sliding window of turns (ADR-005)
_MAX_REWRITE_LEN = 1000  # guard against the model returning the whole prompt back


def _format_history(turns: list[Turn]) -> str:
    lines = []
    for turn in turns:
        lines.append(f"Usuario: {turn.question}")
        lines.append(f"Asistente: {turn.answer}")
    return "\n".join(lines)


@traced("rewrite")
def rewrite_query(
    query: str,
    history: list[Turn],
    llm: ChatLLMPort,
) -> str:
    """Return a standalone version of *query* given *history*.

    Returns *query* unchanged when there is no history or on any LLM failure
    (including timeout — the request timeout lives on *llm*).
    """
    window = history[-_WINDOW:] if history else []

    if not window:
        set_span_attributes(
            original_query=query,
            rewritten_query=query,
            history_turns_used=0,
        )
        return query

    prompt = render(
        load_prompt("rewriter"),
        history=_format_history(window),
        query=query,
    )

    rewritten = query
    try:
        candidate = llm.complete(prompt).strip()
        if candidate and len(candidate) <= _MAX_REWRITE_LEN:
            rewritten = candidate
        else:
            logger.warning("rewrite: empty or oversized output, keeping original query")
    except Exception as exc:
        logger.warning("rewrite: LLM call failed (%s), keeping original query", exc)

    set_span_attributes(
        original_query=query,
        rewritten_query=rewritten,
        history_turns_used=len(window),
    )
    # DEBUG, not INFO: query text may contain PII (CLAUDE.md). Spans still carry
    # original/rewritten_query as required by spec 04 (Phoenix is local-only).
    logger.debug("rewrite: %r -> %r (turns=%d)", query, rewritten, len(window))
    return rewritten
