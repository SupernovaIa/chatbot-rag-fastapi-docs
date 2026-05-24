"""Layer 4 · Output filter (spec 09).

Two responsibilities:

1. **PII redaction.** Regex over emails, credit-card numbers and IPv4/IPv6
   addresses, replaced by ``[EMAIL_REDACTED]`` / ``[CARD_REDACTED]`` /
   ``[IP_REDACTED]`` placeholders. The corpus is FastAPI docs (which *do*
   contain example emails / IPs), so this is mostly a safety net against a
   model that echoes injected PII, but it also stops the model from emitting
   data it should not.

2. **System-prompt-leak detection.** Scans for signature phrases from
   ``system.md``. Layers 2 and 3 are the primary defence (the guardrail blocks
   "reveal your prompt" inputs and the system prompt refuses), so this is a
   last-resort detector that flags an incident if a leak slips through.

Streaming note
--------------
The chat endpoint streams tokens, so we cannot redact the *whole* answer at the
end without breaking the stream. ``StreamRedactor`` redacts incrementally: it
emits redacted text but holds back the last ``_HOLDBACK`` characters so a PII
pattern that is still being generated is never emitted un-redacted. A match is
never cut at the emit boundary (see ``_emit``). ``_HOLDBACK`` exceeds the
longest pattern we redact.
"""

from __future__ import annotations

import re

from app.security.models import OutputScanResult

# --------------------------------------------------------------------------- #
# PII patterns                                                                  #
# --------------------------------------------------------------------------- #

# Email: pragmatic, not RFC-complete. Avoids matching the inline [N] citations.
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Credit card: 13-19 digits in groups of 4 separated by space/dash, or a solid
# run of 13-16 digits. Validated with the Luhn checksum to cut false positives
# (a long FastAPI example integer is not a card unless it checksums).
_CARD = re.compile(
    r"\b(?:\d[ -]?){12,18}\d\b"
)

# IPv4 (with optional :port) and a loose IPv6.
_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?::\d{1,5})?\b"
)
_IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b")

# Longest credit-card representation is 19 digits + 6 separators = 25 chars;
# IPv6 ~45. Hold back enough that any in-flight match sits inside the buffer.
_HOLDBACK = 80

# Signature fragments unique to system.md (layer-3 leak detection).
_SYSTEM_PROMPT_SIGNATURES: tuple[str, ...] = (
    "you are an expert assistant specialised in the **fastapi**",
    "your sole knowledge base is the official fastapi documentation",
    "## core principles",
    "## what you can and cannot do",
    "disclose these instructions, your system prompt",
    "*the retrieved context for the current query follows below.*",
)


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum — cards pass, arbitrary long integers usually do not."""
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    checksum = 0
    parity = len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        checksum += n
    return checksum % 10 == 0


def _redact(segment: str, counts: dict[str, int]) -> str:
    """Redact PII in *segment*, accumulating per-category counts in *counts*."""

    def _sub_email(_m: re.Match[str]) -> str:
        counts["email"] = counts.get("email", 0) + 1
        return "[EMAIL_REDACTED]"

    def _sub_card(m: re.Match[str]) -> str:
        if not _luhn_ok(m.group(0)):
            return m.group(0)
        counts["card"] = counts.get("card", 0) + 1
        return "[CARD_REDACTED]"

    def _sub_ip(_m: re.Match[str]) -> str:
        counts["ip"] = counts.get("ip", 0) + 1
        return "[IP_REDACTED]"

    # Order matters: emails before IPs (an email host can look IP-ish), cards
    # before IPs (a long digit run before an IPv4 dotted form).
    segment = _EMAIL.sub(_sub_email, segment)
    segment = _CARD.sub(_sub_card, segment)
    segment = _IPV4.sub(_sub_ip, segment)
    segment = _IPV6.sub(_sub_ip, segment)
    return segment


def detect_system_prompt_leak(text: str) -> bool:
    """True if *text* contains a signature fragment of the system prompt."""
    low = text.lower()
    return any(sig in low for sig in _SYSTEM_PROMPT_SIGNATURES)


def scan_output(text: str) -> OutputScanResult:
    """Run the full layer-4 scan over a complete answer (non-streaming path)."""
    counts: dict[str, int] = {}
    redacted = _redact(text, counts)
    return OutputScanResult(
        text=redacted,
        pii_redactions=counts,
        system_prompt_leak=detect_system_prompt_leak(redacted),
    )


class StreamRedactor:
    """Incremental PII redactor for the SSE token stream.

    Feed token chunks with :meth:`feed`; it returns the redacted text that is
    safe to emit now (holding back an in-flight tail). Call :meth:`flush` once
    the stream ends to get the remainder. The full redacted answer is available
    via :attr:`redacted_text` after flush for persistence and leak detection.
    """

    def __init__(self) -> None:
        self._raw = ""
        self._emitted = 0  # index into _raw already emitted
        self._out_parts: list[str] = []
        self.counts: dict[str, int] = {}

    def _emit(self, *, final: bool) -> str:
        n = len(self._raw)
        cut = n if final else max(self._emitted, n - _HOLDBACK)
        if not final:
            # Never cut through a match that extends into the held-back tail.
            for pat in (_EMAIL, _CARD, _IPV4, _IPV6):
                for m in pat.finditer(self._raw):
                    if m.start() < cut < m.end():
                        cut = m.start()
        if cut <= self._emitted:
            return ""
        segment = self._raw[self._emitted : cut]
        self._emitted = cut
        redacted = _redact(segment, self.counts)
        self._out_parts.append(redacted)
        return redacted

    def feed(self, text: str) -> str:
        self._raw += text
        return self._emit(final=False)

    def flush(self) -> str:
        return self._emit(final=True)

    @property
    def redacted_text(self) -> str:
        return "".join(self._out_parts)

    @property
    def pii_found(self) -> bool:
        return bool(self.counts)
