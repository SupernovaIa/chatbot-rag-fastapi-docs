"""Fakes for evals unit tests (no Gemini, no pgvector)."""

from __future__ import annotations

from app.evals.ports import JudgeSample
from app.retrieval.models import Candidate, RetrievalResult, Turn


def make_candidate(source: str, section: str, content: str = "") -> Candidate:
    return Candidate(
        chunk_hash=f"{source}:{section}",
        content=content or f"content of {source} / {section}",
        source=source,
        section=section,
        rrf_score=1.0,
    )


class FakeRetriever:
    """Returns a preset candidate list per query; records calls.

    Construct with a mapping ``{question: [Candidate, ...]}`` or a default list.
    """

    def __init__(
        self,
        default: list[Candidate] | None = None,
        by_question: dict[str, list[Candidate]] | None = None,
        fallback_used: bool = False,
        raises: Exception | None = None,
    ) -> None:
        self._default = default or []
        self._by_question = by_question or {}
        self._fallback_used = fallback_used
        self._raises = raises
        self.calls: list[tuple[str, list[Turn]]] = []

    def __call__(self, query: str, history: list[Turn]) -> RetrievalResult:
        self.calls.append((query, history))
        if self._raises is not None:
            raise self._raises
        cands = self._by_question.get(query, self._default)
        return RetrievalResult(
            original_query=query,
            rewritten_query=query,
            candidates=list(cands),
            rerank_fallback_used=self._fallback_used,
        )


class FakeGenerator:
    """Answer generator double. Returns a canned answer (or echoes the query)."""

    def __init__(self, answer: str | None = None, raises: Exception | None = None) -> None:
        self._answer = answer
        self._raises = raises
        self.calls: list[str] = []

    def generate(self, query: str, history: list[Turn], candidates) -> str:
        self.calls.append(query)
        if self._raises is not None:
            raise self._raises
        return self._answer if self._answer is not None else f"answer to: {query}"


class FakeJudge:
    """RAGAS judge double. Returns canned aggregate scores; records sample count."""

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self._scores = scores or {
            "faithfulness": 0.9,
            "answer_relevancy": 0.9,
            "context_precision": 0.85,
            "context_recall": 0.9,
        }
        self.n_samples: int | None = None

    def evaluate(self, samples: list[JudgeSample]) -> dict[str, float]:
        self.n_samples = len(samples)
        return dict(self._scores)
