"""Deterministic retrieval metrics + abstention check (no LLM, no network).

These complement the RAGAS LLM-judged metrics with cheap, reproducible numbers
the gate can trust without any judge variance:

- ``recall_at_k``: fraction of an example's gold chunks present in the top-k.
- ``reciprocal_rank``: 1/rank of the first gold chunk in the retrieved list.
- ``abstention``: whether an answer is a grounded refusal (for ``no_se``).

A retrieved chunk matches a gold chunk when their ``(source, section)`` keys
are equal — the same keys the gold dataset was validated against (spec 08).
"""

from __future__ import annotations

# Refusal markers for the no_se abstention check. The system prompt instructs
# the model to answer "No tengo esa información..." when the corpus lacks it.
_ABSTENTION_MARKERS = (
    "no tengo esa información",
    "no tengo esa informacion",
    "no puedo darte",
    "no aparece en el corpus",
    "fuera del ámbito",
    "fuera del ambito",
    "no está en la documentación",
    "no esta en la documentacion",
)


def recall_at_k(
    retrieved_keys: list[tuple[str, str]],
    gold_keys: set[tuple[str, str]],
    k: int = 5,
) -> float:
    """Fraction of *gold_keys* found within the top-*k* retrieved keys.

    Returns 0.0 for an empty gold set (un-answerable examples are excluded by
    the caller; this guard just avoids a divide-by-zero).
    """
    if not gold_keys:
        return 0.0
    top = set(retrieved_keys[:k])
    return len(top & gold_keys) / len(gold_keys)


def reciprocal_rank(
    retrieved_keys: list[tuple[str, str]],
    gold_keys: set[tuple[str, str]],
) -> float:
    """1/rank of the first retrieved key that is a gold key (0.0 if none)."""
    for i, key in enumerate(retrieved_keys, start=1):
        if key in gold_keys:
            return 1.0 / i
    return 0.0


def is_abstention(answer: str) -> bool:
    """True when *answer* reads as a grounded refusal (no_se behaviour)."""
    low = answer.lower()
    return any(marker in low for marker in _ABSTENTION_MARKERS)


def mean(values: list[float]) -> float | None:
    """Arithmetic mean, or ``None`` for an empty list (metric not applicable)."""
    return sum(values) / len(values) if values else None
