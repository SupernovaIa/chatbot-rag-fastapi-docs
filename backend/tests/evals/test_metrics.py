"""Tests for the deterministic retrieval metrics and abstention check."""

from __future__ import annotations

from app.evals.metrics import (
    is_abstention,
    mean,
    recall_at_k,
    reciprocal_rank,
)

A = ("a.md", "Sec A")
B = ("b.md", "Sec B")
C = ("c.md", "Sec C")


def test_recall_full_when_all_gold_in_top_k() -> None:
    assert recall_at_k([A, B, C], {A, B}, k=5) == 1.0


def test_recall_partial() -> None:
    assert recall_at_k([A, C], {A, B}, k=5) == 0.5


def test_recall_respects_k_cutoff() -> None:
    # Gold chunk sits at position 6 → outside top-5.
    retrieved = [C, C, C, C, C, A]
    assert recall_at_k(retrieved, {A}, k=5) == 0.0


def test_recall_empty_gold_is_zero() -> None:
    assert recall_at_k([A], set(), k=5) == 0.0


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank([A, B], {A}) == 1.0


def test_reciprocal_rank_third_position() -> None:
    assert reciprocal_rank([B, C, A], {A}) == 1.0 / 3


def test_reciprocal_rank_no_hit() -> None:
    assert reciprocal_rank([B, C], {A}) == 0.0


def test_is_abstention_detects_refusal() -> None:
    assert is_abstention("No tengo esa información en la documentación de FastAPI.")
    assert is_abstention("Esa pregunta está fuera del ámbito de esta documentación.")


def test_is_abstention_detects_english_refusal() -> None:
    # The model sometimes refuses in English despite the Spanish system prompt.
    assert is_abstention(
        "I don't have sufficient information in the FastAPI documentation to answer that."
    )
    assert is_abstention("That question is outside the scope of these docs.")


def test_is_abstention_false_for_real_answer() -> None:
    assert not is_abstention("El comando es `fastapi dev`, que activa el auto-reload.")


def test_mean_empty_is_none() -> None:
    assert mean([]) is None
    assert mean([0.5, 1.0]) == 0.75
