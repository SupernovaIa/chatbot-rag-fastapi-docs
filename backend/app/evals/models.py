"""Domain models for the evals feature (pure dataclasses, no ORM)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExampleRun:
    """The pipeline output for one gold example, ready to score.

    ``retrieved_keys`` are the ordered ``(source, section)`` pairs returned by
    retrieval — used for the deterministic recall@k / MRR. ``retrieved_contexts``
    and ``response`` feed the RAGAS judge.
    """

    id: str
    type: str
    question: str
    expected_answer: str
    response: str
    retrieved_contexts: list[str]
    retrieved_keys: list[tuple[str, str]]
    gold_keys: set[tuple[str, str]]
    is_answerable: bool
    rerank_fallback_used: bool = False
    error: str | None = None


@dataclass
class MetricScores:
    """Aggregate metrics for a run. ``None`` means not computed / not applicable."""

    # RAGAS (LLM-judged), over answerable examples.
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    # Deterministic retrieval metrics, over answerable examples.
    recall_at_5: float | None = None
    mrr: float | None = None
    # Custom: abstention rate over no_se examples (refusal detected).
    abstention_rate: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "recall_at_5": self.recall_at_5,
            "mrr": self.mrr,
            "abstention_rate": self.abstention_rate,
        }


@dataclass
class RunReport:
    """Full result of an eval run: per-example records + aggregate metrics."""

    metrics: MetricScores
    runs: list[ExampleRun] = field(default_factory=list)
    commit_sha: str = ""
    corpus_sha: str = ""
    timestamp: str = ""
    subset: str = "full"  # "full" | "ci_subset"

    @property
    def n_total(self) -> int:
        return len(self.runs)

    @property
    def n_answerable(self) -> int:
        return sum(1 for r in self.runs if r.is_answerable)

    @property
    def errors(self) -> list[ExampleRun]:
        return [r for r in self.runs if r.error]
