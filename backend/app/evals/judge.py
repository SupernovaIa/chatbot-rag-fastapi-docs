"""RAGAS judge adapter: Gemini Pro scores the four standard RAG metrics.

ADR-007 picks RAGAS with **Gemini Pro** as judge (the generator stays Gemini
Flash, a different model, to reduce self-approval bias). This adapter wraps the
judge LLM + an embeddings model (``answer_relevancy`` needs embeddings) and runs
RAGAS ``evaluate`` over a batch of samples.

Free-tier discipline (spec 10): concurrency is capped via ``RunConfig`` and the
RAGAS retry/backoff handles transient 429s. The whole adapter degrades loudly —
if RAGAS or the judge is unavailable the caller sees the exception, never a
silently-passing gate.

The heavy ``ragas`` import is deferred to ``evaluate`` so importing this module
(and the rest of ``app.evals``) stays cheap for unit tests that mock the judge.
"""

from __future__ import annotations

import logging
import math

from app.evals.ports import JudgePort, JudgeSample

logger = logging.getLogger(__name__)

# Metric keys the gate reasons about, in report order.
RAGAS_METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


class RagasGeminiJudge:
    """Scores RAGAS metrics with Gemini Pro as the evaluator LLM."""

    def __init__(
        self,
        api_key: str,
        judge_model: str,
        embedding_model: str = "models/gemini-embedding-001",
        max_workers: int = 2,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._judge_model = judge_model
        self._embedding_model = embedding_model
        self._max_workers = max_workers
        self._timeout = timeout

    def evaluate(self, samples: list[JudgeSample]) -> dict[str, float]:
        if not samples:
            return {}

        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
            GoogleGenerativeAIEmbeddings,
        )
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig

        evaluator_llm = LangchainLLMWrapper(
            ChatGoogleGenerativeAI(
                model=self._judge_model,
                google_api_key=self._api_key,
                temperature=0.0,
            )
        )
        evaluator_emb = LangchainEmbeddingsWrapper(
            GoogleGenerativeAIEmbeddings(
                model=self._embedding_model,
                google_api_key=self._api_key,
            )
        )

        dataset = EvaluationDataset(
            samples=[
                SingleTurnSample(
                    user_input=s.question,
                    response=s.response,
                    retrieved_contexts=s.retrieved_contexts or [""],
                    reference=s.expected_answer,
                )
                for s in samples
            ]
        )

        run_config = RunConfig(max_workers=self._max_workers, timeout=self._timeout)
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=evaluator_llm,
            embeddings=evaluator_emb,
            run_config=run_config,
        )

        return _aggregate(result)


def _aggregate(result: object) -> dict[str, float]:
    """Reduce a RAGAS result to per-metric means, dropping NaNs.

    RAGAS returns one score per example per metric; the gate uses the mean.
    Examples that error inside RAGAS surface as NaN and are excluded from the
    mean so one bad row does not silently zero a metric.
    """
    df = result.to_pandas()  # type: ignore[attr-defined]
    out: dict[str, float] = {}
    for key in RAGAS_METRIC_KEYS:
        if key not in df.columns:
            continue
        values = [v for v in df[key].tolist() if v is not None and not _isnan(v)]
        if values:
            out[key] = sum(values) / len(values)
    return out


def _isnan(value: object) -> bool:
    try:
        return math.isnan(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


# Satisfy the Protocol at type-check time.
_j: JudgePort = RagasGeminiJudge.__new__(RagasGeminiJudge)  # type: ignore[assignment]
