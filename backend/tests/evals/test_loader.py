"""Tests for the gold loader and CI subset selection."""

from __future__ import annotations

import pytest

from app.evals.loader import (
    CI_GATE_IDS,
    CI_SUBSET_IDS,
    GoldExample,
    load_gold,
    select_subset,
)


def test_load_gold_parses_all_examples() -> None:
    gold = load_gold()
    assert len(gold) == 40
    assert all(isinstance(e, GoldExample) for e in gold)


def test_no_se_examples_are_unanswerable() -> None:
    gold = load_gold()
    no_se = [e for e in gold if e.type == "no_se"]
    assert no_se
    assert all(not e.is_answerable for e in no_se)
    assert all(e.gold_keys() == set() for e in no_se)


def test_multi_turn_examples_carry_history() -> None:
    gold = load_gold()
    multi = [e for e in gold if e.type == "multi_turn"]
    assert multi
    assert all(e.history for e in multi)
    first = multi[0]
    assert first.history[0].question
    assert first.history[0].answer


def test_answerable_examples_have_gold_keys() -> None:
    gold = load_gold()
    answerable = [e for e in gold if e.type in ("factual", "paraphrase", "multi_source")]
    assert all(e.gold_keys() for e in answerable)


def test_select_subset_covers_all_types_and_preserves_order() -> None:
    gold = load_gold()
    subset = select_subset(gold)
    assert [e.id for e in subset] == list(CI_SUBSET_IDS)
    assert {e.type for e in subset} == {
        "factual", "paraphrase", "multi_source", "no_se", "multi_turn"
    }


def test_ci_gate_subset_is_six_and_covers_all_types() -> None:
    gold = load_gold()
    gate = select_subset(gold, ids=CI_GATE_IDS)
    assert len(gate) == 6
    assert {e.type for e in gate} == {
        "factual", "paraphrase", "multi_source", "no_se", "multi_turn"
    }
    # Must include a multi_source and the no_se (spec 10 gate requirement).
    assert any(e.type == "multi_source" for e in gate)
    assert any(e.type == "no_se" for e in gate)
    # Every gate id is also part of the broader ci_subset.
    assert set(CI_GATE_IDS) <= set(CI_SUBSET_IDS)


def test_select_subset_raises_on_missing_id() -> None:
    gold = load_gold()
    with pytest.raises(ValueError, match="not found"):
        select_subset(gold, ids=("g-01", "does-not-exist"))
