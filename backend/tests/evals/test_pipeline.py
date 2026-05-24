"""Per-example pipeline tests, parametrized over the gold dataset (spec 10).

These run the *runner* over each gold example with deterministic fakes (no
Gemini, no pgvector), so they stay green offline and give per-example pytest
visibility for every type. The representative CI subset is tagged
``@pytest.mark.ci_subset``; the PR workflow's live gate is driven separately by
``python -m app.evals.cli --subset ci_subset`` against the real pipeline.

The retriever fake returns the example's own gold chunks (plus a distractor) so
the structural assertions — answerable flag, gold-key wiring, history pass-through,
abstention shape for ``no_se`` — are exercised without network.
"""

from __future__ import annotations

import pytest

from app.evals.loader import CI_SUBSET_IDS, load_gold
from app.evals.metrics import is_abstention, recall_at_k
from app.evals.runner import run_evals
from tests.evals.conftest import FakeGenerator, FakeJudge, FakeRetriever, make_candidate

_GOLD = {e.id: e for e in load_gold()}


def _param(example_id: str) -> object:
    marks = [pytest.mark.ci_subset] if example_id in CI_SUBSET_IDS else []
    ex = _GOLD[example_id]
    return pytest.param(example_id, id=f"{example_id}-{ex.type}", marks=marks)


ALL_IDS = [_param(i) for i in _GOLD]


def _retriever_for(example) -> FakeRetriever:
    if example.is_answerable:
        cands = [make_candidate(gc.source, gc.section) for gc in example.gold_chunks]
        cands.append(make_candidate("distractor.md", "Irrelevant"))
    else:
        cands = [make_candidate("distractor.md", "Irrelevant")]
    return FakeRetriever(by_question={example.question: cands})


@pytest.mark.parametrize("example_id", ALL_IDS)
def test_example_flows_through_runner(example_id: str) -> None:
    example = _GOLD[example_id]
    answer = example.expected_answer if not example.is_answerable else "grounded answer"
    report = run_evals(
        [example],
        retriever_fn=_retriever_for(example),
        generator=FakeGenerator(answer=answer),
        judge=FakeJudge(),
        use_judge=False,
    )

    assert report.n_total == 1
    run = report.runs[0]
    assert run.error is None
    assert run.id == example_id
    assert run.is_answerable == example.is_answerable

    if example.is_answerable:
        # Gold chunks are retrievable → per-example recall is perfect.
        assert recall_at_k(run.retrieved_keys, run.gold_keys, k=5) == 1.0
        if example.type == "multi_source":
            # Excluded from the deterministic aggregate (label-match too strict).
            assert report.metrics.recall_at_5 is None
        else:
            assert report.metrics.recall_at_5 == 1.0
    else:
        # no_se: excluded from recall, scored by abstention instead.
        assert report.metrics.recall_at_5 is None
        assert is_abstention(run.response)


def test_ci_subset_marker_covers_every_type() -> None:
    subset = [_GOLD[i] for i in CI_SUBSET_IDS]
    assert {e.type for e in subset} == {
        "factual", "paraphrase", "multi_source", "no_se", "multi_turn"
    }
