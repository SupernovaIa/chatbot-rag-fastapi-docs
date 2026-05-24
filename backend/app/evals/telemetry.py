"""Record an eval run as a Phoenix span (spec 10: feed the Quality dashboard).

Emits one ``evals.run`` span carrying the aggregate metrics, the subset, the
commit SHA and the corpus SHA as attributes, plus a child span per example with
its retrieval/abstention outcome. Best-effort: if tracing is disabled or the
collector is unreachable, the OpenTelemetry no-op tracer makes this a no-op
(same contract as ``app.observability.tracing``).
"""

from __future__ import annotations

import logging

from app.evals.models import RunReport
from app.observability.tracing import get_tracer

logger = logging.getLogger(__name__)


def record_eval_run(report: RunReport) -> None:
    """Emit a Phoenix span tree summarising *report*."""
    tracer = get_tracer()
    with tracer.start_as_current_span("evals.run") as span:
        span.set_attribute("evals.subset", report.subset)
        span.set_attribute("evals.commit_sha", report.commit_sha)
        span.set_attribute("evals.corpus_sha", report.corpus_sha)
        span.set_attribute("evals.timestamp", report.timestamp)
        span.set_attribute("evals.n_total", report.n_total)
        span.set_attribute("evals.n_answerable", report.n_answerable)
        span.set_attribute("evals.n_errors", len(report.errors))
        for name, value in report.metrics.as_dict().items():
            if value is not None:
                span.set_attribute(f"evals.metric.{name}", float(value))

        for run in report.runs:
            with tracer.start_as_current_span(f"evals.example.{run.id}") as child:
                child.set_attribute("evals.example.type", run.type)
                child.set_attribute("evals.example.answerable", run.is_answerable)
                child.set_attribute(
                    "evals.example.n_retrieved", len(run.retrieved_keys)
                )
                if run.error:
                    child.set_attribute("evals.example.error", run.error)
