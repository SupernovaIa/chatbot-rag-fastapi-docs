"""Layer 5 (part 1) · Incident logging to Phoenix (spec 09).

Every time a layer blocks or flags a request, ``log_incident`` emits a short
Phoenix span named ``security_incident`` carrying ``blocking_layer`` (the
``BlockingLayer`` value and its name) plus context. This is the audit trail the
red-team checklist and the ``/redteam`` skill read back from Phoenix.

PII is never logged: only a SHA-256 prefix of the offending query is recorded,
never the raw text (CLAUDE.md: "PII redactada antes de loguear").
"""

from __future__ import annotations

import hashlib
import logging

from app.observability.tracing import get_tracer
from app.security.models import BlockingLayer

logger = logging.getLogger(__name__)

# Returned to the user whenever a request is blocked. Deliberately generic: it
# does not reveal which layer fired or why (no oracle for an attacker), and it
# is in Spanish to match the chatbot's response language.
SAFE_RESPONSE = (
    "No puedo ayudarte con esa solicitud. Puedo responder preguntas sobre la "
    "documentación de FastAPI."
)


def query_fingerprint(query: str) -> str:
    """Short, non-reversible fingerprint of a query for correlation in logs."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


def log_incident(
    *,
    layer: BlockingLayer,
    blocked: bool,
    query: str,
    user_id: str,
    session_id: str = "",
    reason: str = "",
    detail: dict[str, object] | None = None,
) -> None:
    """Emit a ``security_incident`` span to Phoenix.

    Parameters
    ----------
    layer:      which defense layer fired.
    blocked:    True if the request was stopped, False if only flagged.
    query:      the offending query (only its fingerprint is recorded).
    user_id:    authenticated user id (for rate-limit / abuse correlation).
    session_id: chat session id, when available.
    reason:     short human-readable reason (e.g. guardrail verdict reason).
    detail:     extra attributes (e.g. PII redaction counts).
    """
    tracer = get_tracer()
    span = tracer.start_span("security_incident")
    try:
        span.set_attribute("blocking_layer", int(layer))
        span.set_attribute("blocking_layer_name", layer.name)
        span.set_attribute("blocked", blocked)
        span.set_attribute("query_fingerprint", query_fingerprint(query))
        span.set_attribute("query_len", len(query))
        span.set_attribute("user_id", user_id)
        if session_id:
            span.set_attribute("session_id", session_id)
        if reason:
            span.set_attribute("reason", reason[:200])
        for key, value in (detail or {}).items():
            span.set_attribute(f"detail.{key}", value)  # type: ignore[arg-type]
    finally:
        span.end()

    logger.info(
        "security_incident layer=%s blocked=%s user=%s fp=%s reason=%s",
        layer.name,
        blocked,
        user_id,
        query_fingerprint(query),
        reason,
    )
