"""Gate decision + Markdown report for an eval run (spec 10).

``evaluate_gate`` applies the thresholds (absolute floor, plus optional relative
regression vs the ``main`` baseline) to a ``RunReport`` and returns a structured
verdict. ``render_markdown`` turns that verdict into the table posted as a PR
comment. ``report_to_baseline`` serialises the gated metrics so the nightly run
can refresh ``baseline_metrics.json``.

Only metrics that were actually computed (non-``None``) are gated; a metric the
runner skipped (e.g. RAGAS disabled) is shown as ``—`` and never fails the gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.evals.models import RunReport

_THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"

# Metrics that BLOCK the merge, in display order. Only the LLM-judged metrics
# gate (spec 10 decision): recall@5 / MRR are reported as advisory because the
# deterministic (source, section) match is too strict for multi_source examples
# (the answer can be fully grounded in non-gold chunks), so they are noisy as a
# hard gate. The judge's context_recall already covers retrieval quality.
_GATED = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)

# Reported in the table but never blocking.
_ADVISORY = ("recall_at_5", "mrr", "abstention_rate")
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


def evaluate_gate(
    report: RunReport,
    thresholds: dict[str, Any] | None = None,
    baseline: dict[str, float] | None = None,
) -> GateVerdict:
    """Apply floors + optional relative regression and return the verdict."""
    thresholds = thresholds or load_thresholds()
    baseline = baseline or {}
    floors: dict[str, float] = thresholds.get("floors", {})
    regression = thresholds.get("regression", {})
    reg_enabled = bool(regression.get("enabled", False))
    # Absolute drop vs the main baseline (e.g. 0.07): block a metric that falls
    # more than this many points below its baseline value, even if still above
    # the floor (guards against slow erosion within judge variance).
    max_drop = float(regression.get("max_absolute_drop", 0.0))

    values = report.metrics.as_dict()
    verdicts: list[MetricVerdict] = []

    for name in _GATED:
        value = values.get(name)
        floor = floors.get(name)
        base = baseline.get(name)

        if value is None:
            # Not computed → not gated (shown as — in the table).
            verdicts.append(MetricVerdict(name, None, floor, base, True, ""))
            continue

        passed = True
        reasons: list[str] = []

        if floor is not None and value < floor:
            passed = False
            reasons.append(f"below floor {floor:.2f}")

        if reg_enabled and base is not None:
            min_allowed = base - max_drop
            if value < min_allowed:
                passed = False
                reasons.append(
                    f"regressed >{max_drop:.2f} vs baseline {base:.3f} "
                    f"(min {min_allowed:.3f})"
                )

        verdicts.append(
            MetricVerdict(name, value, floor, base, passed, "; ".join(reasons))
        )

    return GateVerdict(passed=all(v.passed for v in verdicts), metrics=verdicts)


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "—"


def render_markdown(report: RunReport, verdict: GateVerdict) -> str:
    """Render the PR-comment Markdown table for *report* / *verdict*."""
    status = "✅ **PASS**" if verdict.passed else "❌ **FAIL**"
    lines: list[str] = [
        f"## Evals · {status}",
        "",
        f"Subset: `{report.subset}` · {report.n_total} ejemplos "
        f"({report.n_answerable} answerable) · commit `{report.commit_sha[:8]}` "
        f"· corpus `{report.corpus_sha[:8]}`",
        "",
        "| Métrica | Valor | Floor | Baseline (main) | Estado |",
        "|---|---|---|---|---|",
    ]
    for m in verdict.metrics:
        mark = "✅" if m.passed else f"❌ {m.reason}"
        lines.append(
            f"| {_LABELS[m.name]} | {_fmt(m.value)} | {_fmt(m.floor)} "
            f"| {_fmt(m.baseline)} | {mark} |"
        )

    # Advisory (non-gated) rows: reported for visibility, never block the merge.
    values = report.metrics.as_dict()
    for name in _ADVISORY:
        lines.append(
            f"| {_LABELS[name]} (advisory) | {_fmt(values.get(name))} | — | — | ℹ️ |"
        )

    if report.errors:
        ids = ", ".join(f"`{r.id}`" for r in report.errors)
        lines += ["", f"⚠️ {len(report.errors)} ejemplo(s) con error: {ids}"]

    if not verdict.passed:
        lines += ["", "**Métrica(s) del juez por debajo del umbral — merge bloqueado.**"]

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
