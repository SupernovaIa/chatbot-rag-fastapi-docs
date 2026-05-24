"""Tests for layer 1 (safety settings) and layer 5 (incident logging / rate key)."""

from __future__ import annotations

from langchain_google_genai import HarmBlockThreshold, HarmCategory

from app.security.incidents import log_incident, query_fingerprint
from app.security.models import BlockingLayer
from app.security.rate_limit import check_rate_limit, reset
from app.security.safety import default_safety_settings, is_safety_block


class TestSafetySettings:
    def test_four_content_categories_block_medium_and_above(self) -> None:
        settings = default_safety_settings()
        assert set(settings) == {
            HarmCategory.HARM_CATEGORY_HARASSMENT,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        }
        assert all(t is HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE for t in settings.values())

    def test_is_safety_block(self) -> None:
        assert is_safety_block("SAFETY")
        assert is_safety_block("prohibited_content")
        assert not is_safety_block("STOP")
        assert not is_safety_block(None)


class TestIncidents:
    def test_fingerprint_is_stable_and_non_reversible(self) -> None:
        fp = query_fingerprint("ignore your rules")
        assert len(fp) == 12
        assert fp == query_fingerprint("ignore your rules")
        assert "ignore" not in fp

    def test_log_incident_does_not_raise(self) -> None:
        # Tracing is disabled in tests (no-op span); just assert it's safe.
        log_incident(
            layer=BlockingLayer.GUARDRAIL,
            blocked=True,
            query="hostile thing",
            user_id="user-123",
            session_id="sess-1",
            reason="jailbreak",
            detail={"email": 1},
        )


class TestRateLimit:
    def test_allows_then_blocks_per_user(self, monkeypatch) -> None:
        from app.config import get_settings

        # Force a tiny limit for the test and reset the in-memory window.
        s = get_settings()
        monkeypatch.setattr(s, "rate_limit_per_minute", 3, raising=False)
        reset()

        results = [check_rate_limit("user-A") for _ in range(5)]
        assert results == [True, True, True, False, False]

    def test_limit_is_per_user(self, monkeypatch) -> None:
        from app.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "rate_limit_per_minute", 2, raising=False)
        reset()

        assert check_rate_limit("user-X") is True
        assert check_rate_limit("user-X") is True
        assert check_rate_limit("user-X") is False
        # A different user has an independent budget.
        assert check_rate_limit("user-Y") is True
