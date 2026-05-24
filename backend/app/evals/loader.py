"""Loader for the gold evaluation dataset (spec 08 / spec 10).

Reads ``corpus/sample/fastapi-docs/evals/gold.jsonl`` into ``GoldExample``
objects. The JSONL keys are Spanish (``question_es``, ``expected_answer_es``,
``gold_chunks`` as ``{source, section}``); this module normalises them into a
stable, English-named domain model the runner consumes.

The CI subset (``ci_subset``) is a deterministic, representative slice of the
gold that covers every ``type`` (factual, paraphrase, multi_source, no_se,
multi_turn). It is selected by id so the gate stays reproducible across runs
and the nightly full-suite numbers remain comparable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.retrieval.models import Turn

# Repo-root-relative path to the pinned gold dataset (spec 08).
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOLD_PATH = _REPO_ROOT / "corpus" / "sample" / "fastapi-docs" / "evals" / "gold.jsonl"

# Representative subset that covers all five types. Used by the parametrized
# unit tests (cheap, fakes) and as the mid-tier reference (spec 10).
CI_SUBSET_IDS: tuple[str, ...] = (
    "g-01", "g-02", "g-03", "g-04", "g-05",  # factual
    "g-16", "g-17", "g-18",                   # paraphrase
    "g-24", "g-25",                           # multi_source
    "g-31", "g-32",                           # no_se
    "g-36", "g-37",                           # multi_turn
)

# The 6-example subset the LIVE PR gate runs. Kept at 6 (not 14) so a healthy
# gate finishes under ~10 min on GitHub runners: the Gemini Pro judge is the
# bottleneck (~50s/call), and runner→API latency is higher than local, so the
# full ci_subset overran the CI time budget (spec 10). Covers all five types,
# including one multi_source and the no_se. The gate baseline is measured on
# exactly these ids so the regression check stays apples-to-apples.
CI_GATE_IDS: tuple[str, ...] = (
    "g-01", "g-03",  # factual
    "g-16",          # paraphrase
    "g-24",          # multi_source
    "g-31",          # no_se
    "g-36",          # multi_turn
)


@dataclass(frozen=True)
class GoldChunk:
    """A (source, section) pair identifying an expected gold chunk."""

    source: str
    section: str

    def key(self) -> tuple[str, str]:
        return (self.source, self.section)


@dataclass
class GoldExample:
    """One normalised gold example ready for the eval runner."""

    id: str
    type: str
    question: str
    expected_answer: str
    gold_chunks: list[GoldChunk] = field(default_factory=list)
    history: list[Turn] = field(default_factory=list)
    notes: str = ""

    @property
    def is_answerable(self) -> bool:
        """True when the example expects grounded chunks (``no_se`` → False)."""
        return bool(self.gold_chunks)

    def gold_keys(self) -> set[tuple[str, str]]:
        return {gc.key() for gc in self.gold_chunks}


def _parse_example(raw: dict) -> GoldExample:
    history = [
        Turn(question=t["question_es"], answer=t["answer_es"])
        for t in raw.get("previous_turns", [])
    ]
    chunks = [
        GoldChunk(source=gc["source"], section=gc["section"])
        for gc in raw.get("gold_chunks", [])
    ]
    return GoldExample(
        id=raw["id"],
        type=raw["type"],
        question=raw["question_es"],
        expected_answer=raw["expected_answer_es"],
        gold_chunks=chunks,
        history=history,
        notes=raw.get("notes", ""),
    )


def load_gold(path: Path | str = DEFAULT_GOLD_PATH) -> list[GoldExample]:
    """Load and normalise every gold example from the JSONL file."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [_parse_example(json.loads(line)) for line in lines if line.strip()]


def select_subset(
    examples: list[GoldExample], ids: tuple[str, ...] = CI_SUBSET_IDS
) -> list[GoldExample]:
    """Return the examples whose id is in *ids*, preserving *ids* order.

    Raises if any requested id is missing so a drifted gold fails loudly
    instead of silently shrinking the gate.
    """
    by_id = {e.id: e for e in examples}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"CI subset ids not found in gold: {missing}")
    return [by_id[i] for i in ids]
