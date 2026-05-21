"""Tests for scripts/validate_gold.py.

These tests run offline (skip_db) and cover the schema, distribution and
signature checks, plus a smoke check against the real gold.jsonl.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "validate_gold.py"
_GOLD = _REPO_ROOT / "corpus" / "sample" / "fastapi-docs" / "evals" / "gold.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_gold", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vg = _load_module()


def _valid_example(**overrides):
    base = {
        "id": "g-01",
        "type": "factual",
        "question_es": "¿Pregunta?",
        "expected_answer_es": "Respuesta.",
        "gold_chunks": [{"source": "tutorial/path-params.md", "section": "Path Parameters"}],
        "notes": "nota",
        "reviewed_by": "javi",
        "reviewed_at": "2026-05-21",
    }
    base.update(overrides)
    return base


def _full_dataset():
    """Build a minimal dataset matching the expected distribution."""
    examples = []
    n = 0

    def add(ex_type, count, **extra):
        nonlocal n
        for _ in range(count):
            n += 1
            examples.append(
                _valid_example(id=f"g-{n:02d}", type=ex_type, **extra)
            )

    add("factual", 15)
    add("paraphrase", 8)
    add("multi_source", 7)
    add("no_se", 5, gold_chunks=[], expected_answer_es="No tengo esa información.")
    add(
        "multi_turn",
        5,
        previous_turns=[{"question_es": "q", "answer_es": "a"}],
    )
    return examples


# --- schema ---------------------------------------------------------------


def test_valid_example_passes_schema():
    assert vg.validate_schema([_valid_example()]) == []


def test_missing_field_detected():
    ex = _valid_example()
    del ex["question_es"]
    errors = vg.validate_schema([ex])
    assert any("missing field 'question_es'" in e for e in errors)


def test_wrong_type_detected():
    errors = vg.validate_schema([_valid_example(gold_chunks="nope")])
    assert any("gold_chunks" in e for e in errors)


def test_invalid_type_enum():
    errors = vg.validate_schema([_valid_example(type="weird")])
    assert any("invalid type" in e for e in errors)


def test_unsigned_example_rejected():
    errors = vg.validate_schema([_valid_example(reviewed_by="", reviewed_at="")])
    assert any("reviewed_by" in e for e in errors)
    assert any("reviewed_at" in e for e in errors)


def test_bad_review_date_rejected():
    errors = vg.validate_schema([_valid_example(reviewed_at="ayer")])
    assert any("ISO date" in e for e in errors)


def test_duplicate_id_detected():
    errors = vg.validate_schema([_valid_example(), _valid_example()])
    assert any("duplicate id" in e for e in errors)


def test_no_se_must_have_empty_chunks():
    ex = _valid_example(type="no_se")  # keeps a chunk → invalid
    errors = vg.validate_schema([ex])
    assert any("empty gold_chunks" in e for e in errors)


def test_non_no_se_needs_chunks():
    errors = vg.validate_schema([_valid_example(gold_chunks=[])])
    assert any("at least one gold_chunk" in e for e in errors)


def test_multi_turn_requires_previous_turns():
    errors = vg.validate_schema([_valid_example(type="multi_turn")])
    assert any("previous_turns" in e for e in errors)


def test_gold_chunk_shape_validated():
    errors = vg.validate_schema([_valid_example(gold_chunks=[{"source": "x"}])])
    assert any("'source' and 'section'" in e for e in errors)


# --- distribution ---------------------------------------------------------


def test_distribution_ok():
    assert vg.validate_distribution(_full_dataset()) == []


def test_distribution_wrong_total():
    errors = vg.validate_distribution(_full_dataset()[:-1])
    assert any("expected 40 examples" in e for e in errors)


def test_distribution_wrong_per_type():
    data = _full_dataset()
    data[0]["type"] = "no_se"
    data[0]["gold_chunks"] = []
    errors = vg.validate_distribution(data)
    assert any("factual" in e for e in errors)


# --- real dataset (offline) ------------------------------------------------


@pytest.mark.skipif(not _GOLD.exists(), reason="gold.jsonl not present yet")
def test_real_gold_is_parseable():
    examples, errors = vg.load_examples(_GOLD)
    assert errors == []
    for ex in examples:
        json.dumps(ex)  # round-trips


@pytest.mark.skipif(not _GOLD.exists(), reason="gold.jsonl not present yet")
def test_real_gold_schema_and_distribution():
    errors = vg.validate(_GOLD, database_url="", corpus_sha="", skip_db=True)
    assert errors == [], "\n".join(errors)
