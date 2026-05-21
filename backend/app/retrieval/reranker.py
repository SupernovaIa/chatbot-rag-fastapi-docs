"""LLM-as-reranker (RankGPT, listwise) with a robust fallback.

Spec 03 / ADR-004. The top-K hybrid candidates are sent to Gemini Flash with a
listwise prompt; the model returns a JSON ranking of candidate ids. The parser
is defensive: any malformed output, timeout, or LLM error falls back to the
original hybrid order so retrieval never crashes.
"""

from __future__ import annotations

import json
import logging
import re
import time

from app.observability.tracing import set_span_attributes, traced
from app.retrieval.models import Candidate
from app.retrieval.ports import ChatLLMPort
from app.retrieval.prompts import load_prompt, render

logger = logging.getLogger(__name__)

_CONTENT_TRUNCATE = 500  # chars per candidate (spec 03 default)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _format_candidates(candidates: list[Candidate]) -> str:
    lines = []
    for c in candidates:
        snippet = c.content[:_CONTENT_TRUNCATE].replace("\n", " ").strip()
        lines.append(f"[{c.chunk_hash}] {snippet}")
    return "\n".join(lines)


def _parse_ranking(raw: str, valid_ids: set[str]) -> list[str] | None:
    """Extract an ordered list of known ids from the model output.

    Returns None when nothing usable is found (triggers fallback). Unknown or
    duplicate ids are dropped; missing ids are appended later by the caller.
    """
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None

    ranking = data.get("ranking") if isinstance(data, dict) else None
    if not isinstance(ranking, list):
        return None

    seen: set[str] = set()
    ordered: list[str] = []
    for item in ranking:
        cid = str(item)
        if cid in valid_ids and cid not in seen:
            ordered.append(cid)
            seen.add(cid)
    return ordered or None


def rerank(
    query: str,
    candidates: list[Candidate],
    llm: ChatLLMPort,
    top_k: int = 5,
) -> list[Candidate]:
    """Reorder *candidates* by relevance and return the top *top_k*.

    On any failure (bad JSON, timeout, LLM error) the original order is kept
    and a warning is logged; ``fallback_used`` is recorded on the span. The
    request timeout (spec 03: > 5 s → original order) lives on *llm*.
    """
    top, _ = rerank_with_stats(query, candidates, llm, top_k)
    return top


@traced("rerank")
def rerank_with_stats(
    query: str,
    candidates: list[Candidate],
    llm: ChatLLMPort,
    top_k: int = 5,
) -> tuple[list[Candidate], bool]:
    """Like :func:`rerank` but also returns whether the fallback was used."""
    if not candidates:
        return [], False

    start = time.perf_counter()
    by_id = {c.chunk_hash: c for c in candidates}
    fallback_used = False
    ordered_ids: list[str] | None = None

    prompt = render(
        load_prompt("reranker"),
        query=query,
        candidates=_format_candidates(candidates),
    )

    try:
        raw = llm.complete(prompt)
        ordered_ids = _parse_ranking(raw, set(by_id))
        if ordered_ids is None:
            logger.warning("rerank: unparseable LLM output, falling back to hybrid order")
            fallback_used = True
    except Exception as exc:
        logger.warning("rerank: LLM call failed (%s), falling back to hybrid order", exc)
        fallback_used = True

    if ordered_ids is None:
        ranked = list(candidates)
    else:
        # Append any candidate the model omitted, preserving hybrid order.
        ranked_known = [by_id[cid] for cid in ordered_ids]
        missing = [c for c in candidates if c.chunk_hash not in set(ordered_ids)]
        ranked = ranked_known + missing

    top = ranked[:top_k]
    for position, candidate in enumerate(top, start=1):
        candidate.rerank_position = position

    latency_ms = (time.perf_counter() - start) * 1000.0
    set_span_attributes(
        input_count=len(candidates),
        output_count=len(top),
        latency_ms=round(latency_ms, 2),
        fallback_used=fallback_used,
    )
    logger.info(
        "rerank: in=%d out=%d fallback=%s latency_ms=%.1f",
        len(candidates),
        len(top),
        fallback_used,
        latency_ms,
    )
    return top, fallback_used
