"""Layer 2 · Gemini Flash input guardrail (spec 09).

Classifies the incoming query as legitimate | suspicious | hostile *before* it
reaches retrieval/generation. HOSTILE inputs are blocked; SUSPICIOUS inputs are
answered but flagged. The classifier prompt lives in ``prompts/guardrail.md``.

Availability over strictness: if the guardrail call fails (timeout, parse
error, API down), we *fail open* to LEGITIMATE — the request still passes
through layers 1, 3, 4 and 5. Failing closed would let a flaky free-tier call
take down the whole chat. The ``failed_open`` flag is recorded so it is visible
in tracing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from app.retrieval.ports import ChatLLMPort
from app.security.models import GuardrailVerdict, Verdict

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"
_GUARDRAIL_PROMPT_PATH = _PROMPTS_DIR / "guardrail.md"

_prompt_cache: str | None = None
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _load_prompt() -> str:
    """Load guardrail.md, stripping the YAML front-matter block."""
    global _prompt_cache
    if _prompt_cache is not None:
        return _prompt_cache
    raw = _GUARDRAIL_PROMPT_PATH.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            raw = parts[2].strip()
    _prompt_cache = raw
    return raw


def guardrail_prompt_hash() -> str:
    """Short SHA-256 of the guardrail prompt (for tracing)."""
    return hashlib.sha256(_load_prompt().encode()).hexdigest()[:12]


def _parse_verdict(raw: str) -> GuardrailVerdict:
    """Parse the model's JSON output into a GuardrailVerdict.

    Tolerant of code fences and surrounding prose: extracts the first JSON
    object. On any parse failure, fails open to LEGITIMATE.
    """
    match = _JSON_OBJECT.search(raw)
    if not match:
        logger.warning("Guardrail returned no JSON object: %r", raw[:120])
        return GuardrailVerdict(Verdict.LEGITIMATE, reason="unparseable", failed_open=True)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Guardrail JSON decode failed: %r", match.group(0)[:120])
        return GuardrailVerdict(Verdict.LEGITIMATE, reason="unparseable", failed_open=True)

    raw_verdict = str(data.get("verdict", "")).strip().lower()
    try:
        verdict = Verdict(raw_verdict)
    except ValueError:
        logger.warning("Guardrail unknown verdict %r — failing open", raw_verdict)
        return GuardrailVerdict(Verdict.LEGITIMATE, reason="unknown verdict", failed_open=True)

    return GuardrailVerdict(verdict, reason=str(data.get("reason", ""))[:200])


class InputGuardrail:
    """Layer-2 classifier backed by a Gemini Flash chat adapter."""

    def __init__(self, llm: ChatLLMPort) -> None:
        self._llm = llm

    def classify(self, query: str) -> GuardrailVerdict:
        """Classify *query*. Never raises — fails open to LEGITIMATE on error."""
        prompt = _load_prompt().replace("{query}", query)
        try:
            raw = self._llm.complete(prompt)
        except Exception as exc:  # noqa: BLE001 — fail open on any guardrail error
            logger.warning("Guardrail call failed (%s) — failing open", exc)
            return GuardrailVerdict(Verdict.LEGITIMATE, reason="guardrail error", failed_open=True)
        return _parse_verdict(raw)
