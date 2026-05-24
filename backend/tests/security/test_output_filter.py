"""Tests for layer 4 — PII redaction, streaming redactor, leak detection."""

from __future__ import annotations

from app.security.output_filter import (
    StreamRedactor,
    detect_system_prompt_leak,
    scan_output,
)


class TestScanOutput:
    def test_redacts_email(self) -> None:
        res = scan_output("Contact admin@example.com for help.")
        assert "[EMAIL_REDACTED]" in res.text
        assert "admin@example.com" not in res.text
        assert res.pii_redactions.get("email") == 1
        assert res.redacted

    def test_redacts_valid_credit_card_luhn(self) -> None:
        # 4111 1111 1111 1111 is a canonical Luhn-valid test card.
        res = scan_output("Pay with 4111 1111 1111 1111 today.")
        assert "[CARD_REDACTED]" in res.text
        assert res.pii_redactions.get("card") == 1

    def test_long_integer_that_fails_luhn_is_not_redacted_as_card(self) -> None:
        # An arbitrary long integer in docs must not be treated as a card.
        res = scan_output("The counter reached 1234567890123456 iterations.")
        assert "1234567890123456" in res.text
        assert "card" not in res.pii_redactions

    def test_redacts_ipv4(self) -> None:
        res = scan_output("The server runs at 203.0.113.42 on port 8000.")
        assert "[IP_REDACTED]" in res.text
        assert "203.0.113.42" not in res.text

    def test_clean_text_untouched(self) -> None:
        text = "FastAPI uses Pydantic for validation [1]."
        res = scan_output(text)
        assert res.text == text
        assert not res.redacted

    def test_citation_markers_not_treated_as_pii(self) -> None:
        res = scan_output("This is grounded [1][2] in the docs.")
        assert not res.redacted


class TestLeakDetection:
    def test_detects_system_prompt_signature(self) -> None:
        leaked = (
            "You are an expert assistant specialised in the **FastAPI** web framework."
        )
        assert detect_system_prompt_leak(leaked)

    def test_normal_answer_is_not_a_leak(self) -> None:
        assert not detect_system_prompt_leak(
            "FastAPI declares path parameters with type annotations [1]."
        )


class TestStreamRedactor:
    def test_emits_clean_tokens_progressively(self) -> None:
        r = StreamRedactor()
        out = r.feed("FastAPI is great. " * 10)
        out += r.flush()
        assert "FastAPI is great." in out
        assert not r.pii_found

    def test_redacts_pii_split_across_chunks(self) -> None:
        # Feed an email one character at a time — the holdback must prevent any
        # un-redacted fragment from being emitted.
        r = StreamRedactor()
        emitted = ""
        for ch in "Reach me at secret@evil.com now please, thanks a lot for reading":
            emitted += r.feed(ch)
        emitted += r.flush()
        assert "secret@evil.com" not in emitted
        assert "[EMAIL_REDACTED]" in emitted
        assert r.pii_found
        # The full redacted text equals what was emitted.
        assert r.redacted_text == emitted

    def test_no_pii_leaks_at_chunk_boundary(self) -> None:
        r = StreamRedactor()
        emitted = r.feed("card 4111 1111 ")  # partial card in flight
        emitted += r.feed("1111 1111 done")
        emitted += r.flush()
        assert "4111 1111 1111 1111" not in emitted
        assert "[CARD_REDACTED]" in emitted
