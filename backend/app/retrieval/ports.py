"""Ports (Protocol interfaces) for the retrieval feature.

Thin protocols for the three external dependencies (query embeddings, hybrid
search over pgvector, and the chat LLM used by reranker/rewriter) so tests can
mock them without network or DB access (ADR-011).
"""

from __future__ import annotations

from typing import Protocol

from app.retrieval.models import Candidate


class QueryEmbeddingsPort(Protocol):
    """Embeds a single query string into a dense vector."""

    def embed_query(self, text: str) -> list[float]:
        """Return the embedding for *text* (RETRIEVAL_QUERY task type)."""
        ...


class HybridSearchPort(Protocol):
    """Runs dense + sparse search with RRF fusion in one SQL query."""

    def search(
        self,
        query_vector: list[float],
        query_text: str,
        candidates: int,
        top_k: int,
    ) -> list[Candidate]:
        """Return up to *top_k* candidates ordered by descending RRF score."""
        ...


class ChatLLMPort(Protocol):
    """A minimal chat-completion port for reranker and rewriter prompts.

    The request timeout is a property of the concrete client (set at
    construction), not a per-call argument: the reranker and rewriter receive
    separate clients with their own timeouts.
    """

    def complete(self, prompt: str) -> str:
        """Return the model's text response to *prompt*."""
        ...
