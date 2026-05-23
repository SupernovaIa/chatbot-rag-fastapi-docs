"""Eval runner: run the pipeline over the gold and compute metrics.

For each gold example the runner:
  1. retrieves (rewrite → hybrid → rerank) via the injected ``retriever_fn``,
  2. generates a full answer with the injected ``generator``,
  3. records an ``ExampleRun`` (response, contexts, retrieved keys, gold keys).

Then it aggregates:
  - deterministic ``recall@5`` / ``MRR`` over answerable examples,
  - ``abstention_rate`` over ``no_se`` examples,
  - the four RAGAS metrics via the injected ``judge`` over answerable examples.

Dependencies are injected as a callable + two ports (ADR-011) so the whole run
is unit-testable with fakes — no Gemini, no pgvector. Wiring lives in ``cli``.
A per-example failure is captured on the ``ExampleRun`` and the run continues,
so one flaky call does not abort the whole gate.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.evals.loader import GoldExample
from app.evals.metrics import is_abstention, mean, recall_at_k, reciprocal_rank
from app.evals.models import ExampleRun, MetricScores, RunReport
from app.evals.ports import AnswerGeneratorPort, JudgePort
from app.retrieval.models import RetrievalResult, Turn

logger = logging.getLogger(__name__)

# A retriever takes (query, history) and returns the pipeline result.
RetrieverFn = Callable[[str, list[Turn]], RetrievalResult]


def _run_one(
    example: GoldExample,
    retriever_fn: RetrieverFn,
    generator: AnswerGeneratorPort,
) -> ExampleRun:
    try:
        result = retriever_fn(example.question, example.history)
        candidates = result.candidates
        answer = generator.generate(example.question, example.history, candidates)
        return ExampleRun(
            id=example.id,
            type=example.type,
            question=example.question,
            expected_answer=example.expected_answer,
            response=answer,
            retrieved_contexts=[c.content for c in candidates],
            retrieved_keys=[(c.source, c.section) for c in candidates],
            gold_keys=example.gold_keys(),
            is_answerable=example.is_answerable,
            rerank_fallback_used=result.rerank_fallback_used,
        )
    except Exception as exc:  # noqa: BLE001 — capture, don't abort the run
        logger.warning("Example %s failed: %s", example.id, exc)
        return ExampleRun(
            id=example.id,
            type=example.type,
            question=example.question,
            expected_answer=example.expected_answer,
            response="",
            retrieved_contexts=[],
            retrieved_keys=[],
            gold_keys=example.gold_keys(),
            is_answerable=example.is_answerable,
            error=str(exc),
        )


def run_evals(
    examples: list[GoldExample],
    retriever_fn: RetrieverFn,
    generator: AnswerGeneratorPort,
    judge: JudgePort,
    *,
    top_k: int = 5,
    commit_sha: str = "",
    corpus_sha: str = "",
    subset: str = "full",
    use_judge: bool = True,
) -> RunReport:
    """Run the full eval flow and return an aggregated ``RunReport``."""
    runs = [_run_one(ex, retriever_fn, generator) for ex in examples]

    answerable = [r for r in runs if r.is_answerable and not r.error]
    no_se = [r for r in runs if not r.is_answerable and not r.error]

    recalls = [recall_at_k(r.retrieved_keys, r.gold_keys, k=top_k) for r in answerable]
    rrs = [reciprocal_rank(r.retrieved_keys, r.gold_keys) for r in answerable]
    abstentions = [1.0 if is_abstention(r.response) else 0.0 for r in no_se]

    scores = MetricScores(
        recall_at_5=mean(recalls),
        mrr=mean(rrs),
        abstention_rate=mean(abstentions),
    )

    if use_judge and answerable:
        ragas_scores = judge.evaluate(answerable)
        scores.faithfulness = ragas_scores.get("faithfulness")
        scores.answer_relevancy = ragas_scores.get("answer_relevancy")
        scores.context_precision = ragas_scores.get("context_precision")
        scores.context_recall = ragas_scores.get("context_recall")

    return RunReport(
        metrics=scores,
        runs=runs,
        commit_sha=commit_sha,
        corpus_sha=corpus_sha,
        timestamp=datetime.now(timezone.utc).isoformat(),
        subset=subset,
    )
