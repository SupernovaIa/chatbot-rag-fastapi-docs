"""Retrieval orchestrator: rewrite → embed → hybrid search → rerank.

Wires the three retrieval functions into a single ``retrieve`` call. The whole
run is wrapped in a ``retrieve`` span; each phase emits its own child span.
Only the rewritten query is embedded and searched (spec 04); the original query
travels through unchanged in the result for the downstream generator.
"""

from __future__ import annotations

import logging

from app.observability.tracing import set_span_attributes, traced
from app.retrieval.models import RetrievalResult, Turn
from app.retrieval.ports import ChatLLMPort, HybridSearchPort, QueryEmbeddingsPort
from app.retrieval.reranker import rerank_with_stats
from app.retrieval.rewriter import rewrite_query

logger = logging.getLogger(__name__)


@traced("retrieve")
def retrieve(
    query: str,
    embeddings: QueryEmbeddingsPort,
    searcher: HybridSearchPort,
    rewrite_llm: ChatLLMPort,
    rerank_llm: ChatLLMPort,
    history: list[Turn] | None = None,
    candidates: int = 20,
    top_k: int = 5,
) -> RetrievalResult:
    """Run the full retrieval pipeline and return the reranked top-K.

    *rewrite_llm* and *rerank_llm* are separate clients so each carries its own
    request timeout (spec 03/04); the reranker's timeout degrades to the hybrid
    order on a slow Flash call instead of hanging.
    """
    history = history or []

    rewritten = rewrite_query(query, history, rewrite_llm)
    query_vector = embeddings.embed_query(rewritten)
    hybrid_candidates = searcher.search(
        query_vector=query_vector,
        query_text=rewritten,
        candidates=candidates,
        top_k=candidates,
    )
    top, fallback_used = rerank_with_stats(
        rewritten,
        hybrid_candidates,
        rerank_llm,
        top_k=top_k,
    )

    set_span_attributes(
        original_query=query,
        rewritten_query=rewritten,
        candidates_count=len(hybrid_candidates),
        returned_count=len(top),
    )
    return RetrievalResult(
        original_query=query,
        rewritten_query=rewritten,
        candidates=top,
        rerank_fallback_used=fallback_used,
    )
