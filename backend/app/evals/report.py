"""Gate decision + Markdown report for an eval run (spec 10).

Two distinct checks share the same machinery:

- **PR gate (blocking, deterministic).** ``evaluate_gate`` floors the retrieval
  metrics (recall@5, MRR) computed over the label-matchable answerable examples.
  No LLM judge: it runs in seconds and has no free-tier latency/variance/quota
  risk, so it is safe as a per-PR blocker.
- **Nightly judge monitor (trend, non-blocking for PRs).** ``evaluate_judge``
  floors the RAGAS judge metrics and checks an absolute regression vs the main
  baseline. It runs in ``eval-nightly.yml`` over the full suite; it surfaces
  trends and refreshes the judge baseline, but never blocks a PR.

Only metrics that were actually computed (non-``None``) are gated; a metric the
run skipped is shown as ``—`` and never fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.evals.models import RunReport

_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"

# Deterministic metrics that BLOCK a PR merge, in display order.
_GATE_METRICS = ("recall_at_5", "mrr")
# LLM-judged metrics — monitored nightly, never block a PR.
_JUDGE_METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")

_LABELS = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_precision": "context_precision",
    "context_recall": "context_recall",
    "recall_at_5": "recall@5",
    "mrr": "MRR",
    "abstention_rate": "abstention_rate",
}


@dataclass
class MetricVerdict:
    name: str
    value: float | None
    floor: float | None
    baseline: float | None
    passed: bool
    reason: str  # "" if passed, else why it failed


@dataclass
class GateVerdict:
    passed: bool
    metrics: list[MetricVerdict]

    @property
    def failures(self) -> list[MetricVerdict]:
        return [m for m in self.metrics if not m.passed]


def load_thresholds(path: Path | str = _THRESHOLDS_PATH) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_baseline(path: Path | str | None) -> dict[str, float]:
    """Load baseline metric means from JSON, or ``{}`` if absent."""
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("metrics", data)


def _check(
    report: RunReport,
    metric_names: tuple[str, ...],
    floors: dict[str, float],
    *,
    baseline: dict[str, float] | None = None,
    max_absolute_drop: float = 0.0,
    regression: bool = False,
) -> GateVerdict:
    """Floor (+ optional absolute regression vs baseline) over *metric_names*."""
    baseline = baseline or {}
    values = report.metrics.as_dict()
    verdicts: list[MetricVerdict] = []

    for name in metric_names:
        value = values.get(name)
        floor = floors.get(name)
        base = baseline.get(name)

        if value is None:
            verdicts.append(MetricVerdict(name, None, floor, base, True, ""))
            continue

        passed = True
        reasons: list[str] = []
        if floor is not None and value < floor:
            passed = False
            reasons.append(f"below floor {floor:.2f}")
        if regression and base is not None and value < base - max_absolute_drop:
            passed = False
            reasons.append(
                f"regressed >{max_absolute_drop:.2f} vs baseline {base:.3f} "
                f"(min {base - max_absolute_drop:.3f})"
            )
        verdicts.append(MetricVerdict(name, value, floor, base, passed, "; ".join(reasons)))

    return GateVerdict(passed=all(v.passed for v in verdicts), metrics=verdicts)


def evaluate_gate(report: RunReport, thresholds: dict[str, Any] | None = None) -> GateVerdict:
    """PR gate: floor the deterministic retrieval metrics (recall@5, MRR)."""
    thresholds = thresholds or load_thresholds()
    return _check(report, _GATE_METRICS, thresholds.get("gate", {}))


def evaluate_judge(
    report: RunReport,
    thresholds: dict[str, Any] | None = None,
    baseline: dict[str, float] | None = None,
) -> GateVerdict:
    """Nightly monitor: floor the judge metrics + absolute regression vs baseline."""
    thresholds = thresholds or load_thresholds()
    judge = thresholds.get("judge", {})
    regression = judge.get("regression", {})
    return _check(
        report,
        _JUDGE_METRICS,
        judge.get("floors", {}),
        baseline=baseline,
        max_absolute_drop=float(regression.get("max_absolute_drop", 0.0)),
        regression=bool(regression.get("enabled", False)),
    )


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "—"


def render_markdown(
    report: RunReport,
    verdict: GateVerdict,
    *,
    title: str = "Evals · gate determinista (PR)",
    advisory: tuple[str, ...] = ("abstention_rate",),
    show_baseline: bool = False,
) -> str:
    """Render the Markdown table for *verdict* plus advisory rows."""
    status = "✅ **PASS**" if verdict.passed else "❌ **FAIL**"
    header = "| Métrica | Valor | Floor | Baseline | Estado |" if show_baseline \
        else "| Métrica | Valor | Floor | Estado |"
    sep = "|---|---|---|---|---|" if show_baseline else "|---|---|---|---|"
    lines: list[str] = [
        f"## {title} · {status}",
        "",
        f"Subset: `{report.subset}` · {report.n_total} ejemplos "
        f"({report.n_answerable} answerable) · commit `{report.commit_sha[:8]}` "
        f"· corpus `{report.corpus_sha[:8]}`",
        "",
        header,
        sep,
    ]
    for m in verdict.metrics:
        mark = "✅" if m.passed else f"❌ {m.reason}"
        if show_baseline:
            lines.append(
                f"| {_LABELS[m.name]} | {_fmt(m.value)} | {_fmt(m.floor)} "
                f"| {_fmt(m.baseline)} | {mark} |"
            )
        else:
            lines.append(f"| {_LABELS[m.name]} | {_fmt(m.value)} | {_fmt(m.floor)} | {mark} |")

    values = report.metrics.as_dict()
    extra_cols = "| — | — |" if show_baseline else "| — |"
    for name in advisory:
        val = values.get(name)
        if val is None:
            continue
        lines.append(f"| {_LABELS[name]} (advisory) | {_fmt(val)} {extra_cols} ℹ️ |")

    if report.errors:
        ids = ", ".join(f"`{r.id}`" for r in report.errors)
        lines += ["", f"⚠️ {len(report.errors)} ejemplo(s) con error: {ids}"]
    if not verdict.passed:
        lines += ["", "**Métrica(s) por debajo del umbral — merge bloqueado.**"]

    return "\n".join(lines) + "\n"


def report_to_baseline(report: RunReport) -> dict[str, Any]:
    """Serialise the run as a baseline JSON payload (for the nightly refresh)."""
    return {
        "commit_sha": report.commit_sha,
        "corpus_sha": report.corpus_sha,
        "timestamp": report.timestamp,
        "subset": report.subset,
        "metrics": {k: v for k, v in report.metrics.as_dict().items() if v is not None},
    }
