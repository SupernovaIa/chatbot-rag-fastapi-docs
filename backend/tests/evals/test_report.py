"""Tests for the deterministic PR gate and the nightly judge monitor."""

from __future__ import annotations

from app.evals.models import ExampleRun, MetricScores, RunReport
from app.evals.report import (
    evaluate_gate,
    evaluate_judge,
    load_thresholds,
    render_markdown,
    report_to_baseline,
)

THRESHOLDS = {
    "gate": {"recall_at_5": 0.85, "mrr": 0.85},
    "judge": {
        "floors": {
            "faithfulness": 0.80,
            "answer_relevancy": 0.70,
            "context_precision": 0.80,
            "context_recall": 0.85,
        },
        "regression": {"enabled": True, "max_absolute_drop": 0.07},
    },
    "advisory": {"abstention_rate": 0.80},
}


def _report(**overrides) -> RunReport:
    base = dict(
        faithfulness=0.95, answer_relevancy=0.85, context_precision=0.98,
        context_recall=0.96, recall_at_5=1.0, mrr=1.0,
    )
    base.update(overrides)
    return RunReport(metrics=MetricScores(**base), subset="ci_gate")


# --- thresholds file ---

def test_thresholds_yaml_has_gate_and_judge_sections() -> None:
    t = load_thresholds()
    assert set(t["gate"]) == {"recall_at_5", "mrr"}
    assert set(t["judge"]["floors"]) == {
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    }
    assert t["judge"]["regression"]["enabled"] is True


# --- deterministic PR gate (recall@5, MRR) ---

def test_pr_gate_passes_above_floor() -> None:
    assert evaluate_gate(_report(), thresholds=THRESHOLDS).passed


def test_pr_gate_blocks_when_recall_below_floor() -> None:
    # One of four label-matchable examples loses its gold chunk -> recall 0.75.
    verdict = evaluate_gate(_report(recall_at_5=0.75), thresholds=THRESHOLDS)
    assert not verdict.passed
    assert {m.name for m in verdict.failures} == {"recall_at_5"}


def test_pr_gate_blocks_when_mrr_below_floor() -> None:
    verdict = evaluate_gate(_report(mrr=0.80), thresholds=THRESHOLDS)
    assert not verdict.passed
    assert {m.name for m in verdict.failures} == {"mrr"}


def test_pr_gate_ignores_judge_metrics() -> None:
    # Judge metrics tanked must NOT affect the deterministic PR gate.
    verdict = evaluate_gate(_report(faithfulness=0.1, context_recall=0.1), thresholds=THRESHOLDS)
    assert verdict.passed
    assert {m.name for m in verdict.metrics} == {"recall_at_5", "mrr"}


# --- nightly judge monitor ---

def test_judge_monitor_passes_at_baseline() -> None:
    base = {"faithfulness": 0.95, "answer_relevancy": 0.85,
            "context_precision": 0.98, "context_recall": 0.96}
    assert evaluate_judge(_report(), thresholds=THRESHOLDS, baseline=base).passed


def test_judge_monitor_flags_floor_break() -> None:
    verdict = evaluate_judge(_report(context_recall=0.70), thresholds=THRESHOLDS)
    assert not verdict.passed
    assert any(m.name == "context_recall" for m in verdict.failures)


def test_judge_monitor_flags_absolute_regression() -> None:
    base = {"faithfulness": 0.95}
    # 0.86 is above the 0.80 floor but a 0.09 drop (>0.07) from baseline.
    verdict = evaluate_judge(_report(faithfulness=0.86), thresholds=THRESHOLDS, baseline=base)
    assert not verdict.passed
    assert any("regressed" in m.reason for m in verdict.failures)


def test_judge_monitor_excludes_retrieval_metrics() -> None:
    assert {m.name for m in evaluate_judge(_report(), thresholds=THRESHOLDS).metrics} == {
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    }


# --- rendering ---

def test_render_pr_gate_shows_retrieval_and_advisory() -> None:
    report = _report(abstention_rate=1.0)
    md = render_markdown(report, evaluate_gate(report, thresholds=THRESHOLDS))
    assert "recall@5" in md and "MRR" in md
    assert "abstention_rate" in md
    assert "faithfulness" not in md  # judge metrics are not in the PR gate table


def test_render_flags_errors() -> None:
    report = _report()
    report.runs = [
        ExampleRun(id="g-99", type="factual", question="q", expected_answer="e",
                   response="", retrieved_contexts=[], retrieved_keys=[], gold_keys=set(),
                   is_answerable=True, error="timeout")
    ]
    md = render_markdown(report, evaluate_gate(report, thresholds=THRESHOLDS))
    assert "g-99" in md and "error" in md.lower()


def test_report_to_baseline_drops_none_metrics() -> None:
    payload = report_to_baseline(_report(faithfulness=None))
    assert "faithfulness" not in payload["metrics"]
    assert payload["metrics"]["recall_at_5"] == 1.0
