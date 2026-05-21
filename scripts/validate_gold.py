#!/usr/bin/env python3
"""Validate the gold evaluation dataset.

Checks, in order:
    1. Every line in gold.jsonl parses as JSON.
    2. Each example complies with the schema (required fields, types, enums).
    3. The type distribution matches the agreed quotas.
    4. Every example is signed (reviewed_by + reviewed_at).
    5. Every gold_chunk (source, section) exists in pgvector for the current
       corpus SHA. Skipped for `no_se` examples (which carry no chunks).

Usage (from repo root or inside the Docker container):
    python scripts/validate_gold.py [--gold PATH] [--corpus-sha SHA] [--skip-db]

Environment variables:
    DATABASE_URL    Postgres connection string (default: Docker service).
    CORPUS_SHA      Corpus commit SHA (default: pinned SHA in SOURCE.md).

Exit code 0 if the dataset is valid, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_GOLD = _REPO_ROOT / "corpus" / "sample" / "fastapi-docs" / "evals" / "gold.jsonl"
_DEFAULT_CORPUS_SHA = "40e33e492dbf4af6172997f4e3238a32e56cbe26"
_DATABASE_URL_DEFAULT = "postgresql+psycopg://postgres:postgres@localhost:5432/chatbot_rag"

VALID_TYPES = {"factual", "paraphrase", "multi_source", "no_se", "multi_turn"}
EXPECTED_DISTRIBUTION = {
    "factual": 15,
    "paraphrase": 8,
    "multi_source": 7,
    "no_se": 5,
    "multi_turn": 5,
}
REQUIRED_FIELDS = {
    "id": str,
    "type": str,
    "question_es": str,
    "expected_answer_es": str,
    "gold_chunks": list,
    "notes": str,
    "reviewed_by": str,
    "reviewed_at": str,
}


def load_examples(gold_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse JSONL. Returns (examples, errors)."""
    errors: list[str] = []
    examples: list[dict[str, Any]] = []
    if not gold_path.exists():
        return [], [f"gold file not found: {gold_path}"]
    for lineno, raw in enumerate(gold_path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            examples.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON: {exc}")
    return examples, errors


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def validate_schema(examples: list[dict[str, Any]]) -> list[str]:
    """Validate fields, types, enums, signature and per-type extra rules."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, ex in enumerate(examples):
        tag = ex.get("id", f"<index {i}>")

        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in ex:
                errors.append(f"{tag}: missing field '{field}'")
            elif not isinstance(ex[field], expected_type):
                errors.append(
                    f"{tag}: field '{field}' must be {expected_type.__name__}, "
                    f"got {type(ex[field]).__name__}"
                )

        ex_id = ex.get("id")
        if isinstance(ex_id, str):
            if ex_id in seen_ids:
                errors.append(f"{tag}: duplicate id")
            seen_ids.add(ex_id)

        ex_type = ex.get("type")
        if ex_type not in VALID_TYPES:
            errors.append(f"{tag}: invalid type '{ex_type}'")

        # Signature is mandatory for every example.
        if not ex.get("reviewed_by"):
            errors.append(f"{tag}: empty 'reviewed_by' (unsigned example)")
        reviewed_at = ex.get("reviewed_at")
        if not reviewed_at:
            errors.append(f"{tag}: empty 'reviewed_at' (unsigned example)")
        elif isinstance(reviewed_at, str) and not _is_iso_date(reviewed_at):
            errors.append(f"{tag}: 'reviewed_at' is not an ISO date: {reviewed_at!r}")

        # gold_chunks shape: {source, section} objects (empty allowed for no_se).
        chunks = ex.get("gold_chunks", [])
        if isinstance(chunks, list):
            for j, ch in enumerate(chunks):
                if not isinstance(ch, dict) or "source" not in ch or "section" not in ch:
                    errors.append(
                        f"{tag}: gold_chunks[{j}] must have 'source' and 'section'"
                    )

        # Per-type rules.
        if ex_type == "no_se":
            if chunks:
                errors.append(f"{tag}: 'no_se' must have empty gold_chunks")
        else:
            if isinstance(chunks, list) and not chunks:
                errors.append(f"{tag}: '{ex_type}' must have at least one gold_chunk")

        if ex_type == "multi_turn":
            turns = ex.get("previous_turns")
            if not isinstance(turns, list) or not turns:
                errors.append(f"{tag}: 'multi_turn' must have non-empty 'previous_turns'")
            else:
                for j, turn in enumerate(turns):
                    if (
                        not isinstance(turn, dict)
                        or "question_es" not in turn
                        or "answer_es" not in turn
                    ):
                        errors.append(
                            f"{tag}: previous_turns[{j}] must have "
                            f"'question_es' and 'answer_es'"
                        )

    return errors


def validate_distribution(examples: list[dict[str, Any]]) -> list[str]:
    """Check counts per type and total."""
    errors: list[str] = []
    counts = Counter(ex.get("type") for ex in examples)
    total = sum(EXPECTED_DISTRIBUTION.values())
    if len(examples) != total:
        errors.append(f"expected {total} examples, found {len(examples)}")
    for ex_type, expected in EXPECTED_DISTRIBUTION.items():
        actual = counts.get(ex_type, 0)
        if actual != expected:
            errors.append(
                f"distribution: type '{ex_type}' expected {expected}, found {actual}"
            )
    return errors


def validate_chunks_in_db(
    examples: list[dict[str, Any]], database_url: str, corpus_sha: str
) -> list[str]:
    """Check every gold_chunk exists in pgvector for the given corpus_sha."""
    from sqlalchemy import create_engine, text

    errors: list[str] = []
    engine = create_engine(database_url, pool_pre_ping=True)
    query = text(
        """
        SELECT 1 FROM chunks
        WHERE corpus_sha = :sha
          AND metadata->>'source' = :source
          AND metadata->>'section' = :section
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            present = conn.execute(
                text("SELECT 1 FROM chunks WHERE corpus_sha = :sha LIMIT 1"),
                {"sha": corpus_sha},
            ).first()
            if present is None:
                errors.append(
                    f"no chunks found in pgvector for corpus_sha {corpus_sha!r}; "
                    f"is the corpus indexed?"
                )
                return errors

            for ex in examples:
                tag = ex.get("id", "<?>")
                for ch in ex.get("gold_chunks", []):
                    if not isinstance(ch, dict):
                        continue
                    row = conn.execute(
                        query,
                        {
                            "sha": corpus_sha,
                            "source": ch.get("source"),
                            "section": ch.get("section"),
                        },
                    ).first()
                    if row is None:
                        errors.append(
                            f"{tag}: gold_chunk not found in pgvector "
                            f"(source={ch.get('source')!r}, "
                            f"section={ch.get('section')!r})"
                        )
    finally:
        engine.dispose()
    return errors


def validate(
    gold_path: Path,
    *,
    database_url: str,
    corpus_sha: str,
    skip_db: bool = False,
) -> list[str]:
    """Run all checks and return a flat list of error messages."""
    examples, errors = load_examples(gold_path)
    if errors:
        return errors  # cannot continue if JSONL is broken
    errors += validate_schema(examples)
    errors += validate_distribution(examples)
    if not skip_db:
        errors += validate_chunks_in_db(examples, database_url, corpus_sha)
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=_DEFAULT_GOLD)
    parser.add_argument(
        "--corpus-sha",
        default=os.environ.get("CORPUS_SHA", _DEFAULT_CORPUS_SHA),
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip the pgvector chunk-existence check (offline validation).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL", _DATABASE_URL_DEFAULT)
    errors = validate(
        args.gold,
        database_url=database_url,
        corpus_sha=args.corpus_sha,
        skip_db=args.skip_db,
    )
    if errors:
        print(f"❌ gold dataset INVALID — {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("✅ gold dataset valid (40 examples, distribution OK, all chunks present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
