"""Domain models for the retrieval feature (pure dataclasses, no ORM)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    """One conversational turn used by the multi-turn rewriter (ADR-005).

    Mirrors the shape of ``previous_turns`` in the gold dataset.
    """

    question: str
    answer: str


@dataclass
class Candidate:
    """A retrieved chunk with its ranking signals across pipeline phases."""

    chunk_hash: str
    content: str
    source: str
    section: str
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rrf_score: float = 0.0
    rerank_position: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Output of the orchestrator: the final top-K plus pipeline diagnostics."""

    original_query: str
    rewritten_query: str
    candidates: list[Candidate]  # final reranked top-K
    rerank_fallback_used: bool = False
