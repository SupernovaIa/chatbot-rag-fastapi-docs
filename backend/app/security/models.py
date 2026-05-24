"""Shared types for the defense-in-depth security layers (spec 09).

The five layers each map to a ``BlockingLayer`` value so that, when a request is
stopped, the incident logged to Phoenix records *which* layer cut it
(``blocking_layer`` attribute). ``GuardrailVerdict`` is the output of layer 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class BlockingLayer(IntEnum):
    """The defense layer that blocked (or flagged) a request.

    Numbered 1..5 to match the spec. ``NONE`` means the request passed every
    layer cleanly.
    """

    NONE = 0
    SAFETY_FILTER = 1  # Gemini safety settings blocked the generation
    GUARDRAIL = 2  # Flash guardrail classified the input as hostile
    SYSTEM_PROMPT = 3  # the model refused via the hardened system prompt
    OUTPUT_FILTER = 4  # output filter redacted PII / detected a leak
    RATE_LIMIT = 5  # per-user rate limit exceeded


class Verdict(StrEnum):
    """Layer-2 guardrail classification of an incoming user query."""

    LEGITIMATE = "legitimate"
    SUSPICIOUS = "suspicious"
    HOSTILE = "hostile"


@dataclass(frozen=True)
class GuardrailVerdict:
    """Result of the layer-2 input guardrail.

    ``blocked`` is True only for HOSTILE. SUSPICIOUS passes through with
    ``flagged=True`` so the turn is generated but the incident is recorded.
    ``failed_open`` is True when the guardrail call errored and we defaulted to
    LEGITIMATE (availability over strictness — the deeper layers still apply).
    """

    verdict: Verdict
    reason: str = ""
    failed_open: bool = False

    @property
    def blocked(self) -> bool:
        return self.verdict is Verdict.HOSTILE

    @property
    def flagged(self) -> bool:
        return self.verdict is Verdict.SUSPICIOUS


@dataclass
class OutputScanResult:
    """Result of scanning a generated answer through the layer-4 output filter."""

    text: str
    pii_redactions: dict[str, int] = field(default_factory=dict)
    system_prompt_leak: bool = False

    @property
    def redacted(self) -> bool:
        return bool(self.pii_redactions) or self.system_prompt_leak

    @property
    def total_redactions(self) -> int:
        return sum(self.pii_redactions.values())
