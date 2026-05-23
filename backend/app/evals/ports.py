"""Ports (Protocol interfaces) for the evals feature (ADR-011).

Two external dependencies sit behind thin protocols so the runner is unit
testable with fakes (no Gemini, no pgvector):

- ``AnswerGeneratorPort``: produces the assistant answer for one example.
- ``JudgePort``: scores a batch of samples with RAGAS metrics.

Retrieval itself is reused from ``app.retrieval`` (its own ports already cover
embeddings / hybrid search / chat LLM), so it is injected as a callable.
"""

from __future__ import annotations

from typing import Protocol

from app.retrieval.models import Candidate, Turn


class AnswerGeneratorPort(Protocol):
    """Generates a full (non-streaming) answer grounded in the candidates."""

    def generate(
        self, query: str, history: list[Turn], candidates: list[Candidate]
    ) -> str:
        """Return the assistant's complete answer text."""
        ...


class JudgeSample(Protocol):
    """Read-only view of what the judge needs per example (duck-typed)."""

    question: str
    expected_answer: str
    response: str
    retrieved_contexts: list[str]


class JudgePort(Protocol):
    """Scores RAGAS metrics over a batch and returns aggregate means.

    Returns a dict keyed by ``faithfulness``, ``answer_relevancy``,
    ``context_precision``, ``context_recall`` (values are floats, or absent /
    NaN-free as the adapter normalises them).
    """

    def evaluate(self, samples: list[JudgeSample]) -> dict[str, float]:
        ...
