"""Retrieval gating · Gemini Flash intent classifier (spec 14, ADR-013).

Decides whether a turn needs to retrieve documentation context from the corpus
*before* the ``rewrite → retrieve → rerank`` pipeline runs. Greetings, thanks,
meta-questions about the conversation and follow-ups answerable from history are
skipped (answered directly); everything else retrieves. The classifier prompt
lives in ``prompts/intent_gate.md``.

Runs **concurrently** with the layer-2 guardrail (router.py): both are Flash
calls on the input path, launched together with ``asyncio.gather`` so the input
latency is ``max(guardrail, intent)`` rather than the sum (ADR-013).

Fail-open toward *retrieve*: if the classifier call fails (timeout, parse error,
API down) we default to ``needs_retrieval=True``. Skipping retrieval when it was
actually needed (answering a technical question ungrounded) is the costly
failure, so both the prompt and the error path are biased toward retrieving. The
``failed_open`` flag is recorded so it is visible in tracing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.retrieval.models import Turn
from app.retrieval.ports import ChatLLMPort

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"
_INTENT_PROMPT_PATH = _PROMPTS_DIR / "intent_gate.md"

_prompt_cache: str | None = None
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class IntentVerdict:
    """Result of the retrieval-gating intent classifier.

    ``needs_retrieval`` drives the gate: True runs the full pipeline, False
    skips it and answers directly. ``failed_open`` is True when the classifier
    errored and we defaulted to retrieving (the safe default).
    """

    needs_retrieval: bool
    reason: str = ""
    failed_open: bool = False


def _load_prompt() -> str:
    """Load intent_gate.md, stripping the YAML front-matter block."""
    global _prompt_cache
    if _prompt_cache is not None:
        return _prompt_cache
    raw = _INTENT_PROMPT_PATH.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            raw = parts[2].strip()
    _prompt_cache = raw
    return raw


def intent_prompt_hash() -> str:
    """Short SHA-256 of the intent prompt (for tracing)."""
    return hashlib.sha256(_load_prompt().encode()).hexdigest()[:12]


def _format_history(history: list[Turn]) -> str:
    if not history:
        return "(no previous turns)"
    lines: list[str] = []
    for turn in history:
        lines.append(f"User: {turn.question}")
        lines.append(f"Assistant: {turn.answer}")
    return "\n".join(lines)


def _parse_verdict(raw: str) -> IntentVerdict:
    """Parse the model's JSON output into an IntentVerdict.

    Tolerant of code fences and surrounding prose: extracts the first JSON
    object. On any parse failure, fails open to *retrieve*.
    """
    match = _JSON_OBJECT.search(raw)
    if not match:
        logger.warning("Intent gate returned no JSON object: %r", raw[:120])
        return IntentVerdict(needs_retrieval=True, reason="unparseable", failed_open=True)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Intent gate JSON decode failed: %r", match.group(0)[:120])
        return IntentVerdict(needs_retrieval=True, reason="unparseable", failed_open=True)

    if "needs_retrieval" not in data:
        logger.warning("Intent gate missing needs_retrieval — retrieving")
        return IntentVerdict(needs_retrieval=True, reason="missing field", failed_open=True)

    return IntentVerdict(
        needs_retrieval=bool(data.get("needs_retrieval")),
        reason=str(data.get("reason", ""))[:200],
    )


class IntentGate:
    """Retrieval-gating classifier backed by a Gemini Flash chat adapter."""

    def __init__(self, llm: ChatLLMPort) -> None:
        self._llm = llm

    def classify(self, query: str, history: list[Turn] | None = None) -> IntentVerdict:
        """Classify *query*. Never raises — fails open to *retrieve* on error."""
        prompt = (
            _load_prompt()
            .replace("{history}", _format_history(history or []))
            .replace("{query}", query)
        )
        try:
            raw = self._llm.complete(prompt)
        except Exception as exc:  # noqa: BLE001 — fail open (retrieve) on any error
            logger.warning("Intent gate call failed (%s) — retrieving", exc)
            return IntentVerdict(needs_retrieval=True, reason="gate error", failed_open=True)
        return _parse_verdict(raw)
