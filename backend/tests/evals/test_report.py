"""Tests for the gate decision and Markdown report."""

from __future__ import annotations

from app.evals.models import ExampleRun, MetricScores, RunReport
from app.evals.report import (
    evaluate_gate,
    load_thresholds,
    render_markdown,
    report_to_baseline,
)

# A thresholds dict mirroring thresholds.yaml shape, kept local so the test is
# independent of future tuning of the real file.
THRESHOLDS = {
    "floors": {
        "faithfulness": 0.75,
        "answer_relevancy": 0.80,
        "context_precision": 0.70,
        "context_recall": 0.80,
    },
    "advisory": {"recall_at_5": 0.85, "mrr": 0.60, "abstention_rate": 0.80},
    "regression": {"enabled": True, "max_relative_drop": 0.05},
}


def _report(**overrides) -> RunReport:
    base = dict(
        faithfulness=0.9,
        answer_relevancy=0.9,
        context_precision=0.8,
        context_recall=0.9,
        recall_at_5=0.9,
        mrr=0.8,
    )
    base.update(overrides)
    return RunReport(metrics=MetricScores(**base), subset="ci_subset")


def test_thresholds_yaml_loads_with_expected_keys() -> None:
    t = load_thresholds()
    # Only the four LLM-judged metrics gate; recall@5 / MRR are advisory.
    assert set(t["floors"]) == {
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    }
    assert {"recall_at_5", "mrr"} <= set(t["advisory"])


def test_gate_passes_when_all_above_floor() -> None:
    verdict = evaluate_gate(_report(), thresholds=THRESHOLDS)
    assert verdict.passed
    assert verdict.failures == []


def test_gate_fails_below_floor() -> None:
    verdict = evaluate_gate(_report(faithfulness=0.5), thresholds=THRESHOLDS)
    assert not verdict.passed
    failed = {m.name for m in verdict.failures}
    assert failed == {"faithfulness"}
    assert "below floor" in verdict.failures[0].reason


def test_gate_fails_on_relative_regression_even_above_floor() -> None:
    # faithfulness 0.80 is above the 0.75 floor but a >5% drop from baseline 0.95.
    baseline = {"faithfulness": 0.95}
    verdict = evaluate_gate(_report(faithfulness=0.80), thresholds=THRESHOLDS, baseline=baseline)
    assert not verdict.passed
    assert any("regressed" in m.reason for m in verdict.failures)


def test_gate_tolerates_small_drop_within_margin() -> None:
    baseline = {"faithfulness": 0.90}
    # 0.88 is within 5% of 0.90 (min allowed 0.855) and above the floor.
    verdict = evaluate_gate(_report(faithfulness=0.88), thresholds=THRESHOLDS, baseline=baseline)
    assert verdict.passed


def test_recall_and_mrr_are_advisory_not_gated() -> None:
    # recall@5 / MRR well below their reference values must NOT block the gate.
    verdict = evaluate_gate(_report(recall_at_5=0.10, mrr=0.10), thresholds=THRESHOLDS)
    assert verdict.passed
    gated = {m.name for m in verdict.metrics}
    assert "recall_at_5" not in gated
    assert "mrr" not in gated


def test_uncomputed_metric_is_not_gated() -> None:
    verdict = evaluate_gate(_report(faithfulness=None), thresholds=THRESHOLDS)
    assert verdict.passed
    faith = next(m for m in verdict.metrics if m.name == "faithfulness")
    assert faith.value is None
    assert faith.passed


def test_render_markdown_shows_status_and_metrics() -> None:
    report = _report()
    verdict = evaluate_gate(report, thresholds=THRESHOLDS)
    md = render_markdown(report, verdict)
    assert "PASS" in md
    assert "faithfulness" in md
    assert "recall@5" in md
    assert "abstention_rate" in md


def test_render_markdown_flags_errors() -> None:
    report = _report()
    report.runs = [
        ExampleRun(
            id="g-99", type="factual", question="q", expected_answer="e",
            response="", retrieved_contexts=[], retrieved_keys=[], gold_keys=set(),
            is_answerable=True, error="timeout",
        )
    ]
    verdict = evaluate_gate(report, thresholds=THRESHOLDS)
    md = render_markdown(report, verdict)
    assert "g-99" in md
    assert "error" in md.lower()


def test_report_to_baseline_drops_none_metrics() -> None:
    report = _report(faithfulness=None)
    payload = report_to_baseline(report)
    assert "faithfulness" not in payload["metrics"]
    assert payload["metrics"]["recall_at_5"] == 0.9
    assert payload["subset"] == "ci_subset"
