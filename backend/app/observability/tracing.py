"""OpenTelemetry → Phoenix tracing setup and the ``@traced`` helper.

Per ADR-008, the backend exports spans to a self-hosted Phoenix collector
(OTLP, port 6006) and instruments LangChain natively via OpenInference. Each
pipeline phase (rewrite, hybrid_search, rerank, retrieve) emits a span.

Design notes
------------
- ``setup_tracing`` is idempotent and *defensive*: if the tracing libraries or
  the collector are unavailable, it logs a warning and the app keeps running.
  Unit tests therefore need no Phoenix instance — spans become no-ops.
- ``@traced`` wraps a function in a span. Inside the function, call
  ``set_span_attributes`` to attach phase-specific attributes (the spec lists
  the required keys per phase).
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any, Callable, TypeVar

from opentelemetry import trace

logger = logging.getLogger(__name__)

_PROJECT_NAME = "chatbot-rag-fastapi-docs"
_TRACER_NAME = "app.retrieval"

_initialised = False


def setup_tracing(
    endpoint: str | None = None,
    project_name: str = _PROJECT_NAME,
) -> bool:
    """Register the Phoenix OTLP exporter and instrument LangChain.

    Returns True if tracing was set up, False if it was skipped (missing libs,
    unreachable collector, or already initialised). Never raises.
    """
    global _initialised
    if _initialised:
        return True

    if os.environ.get("DISABLE_TRACING") == "1":
        logger.info("Tracing disabled via DISABLE_TRACING=1")
        return False

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            project_name=project_name,
            endpoint=f"{endpoint.rstrip('/')}/v1/traces" if endpoint else None,
            set_global_tracer_provider=True,
            batch=True,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        _initialised = True
        logger.info("Tracing initialised (Phoenix endpoint=%s)", endpoint)
        return True
    except Exception as exc:  # pragma: no cover - defensive, env-dependent
        logger.warning(
            "Tracing setup skipped (%s). Pipeline runs without Phoenix spans.", exc
        )
        return False


def get_tracer() -> trace.Tracer:
    """Return the tracer for the retrieval pipeline.

    Works even when ``setup_tracing`` was never called: the OpenTelemetry API
    falls back to a no-op tracer, so ``@traced`` is always safe.
    """
    return trace.get_tracer(_TRACER_NAME)


def set_span_attributes(**attributes: Any) -> None:
    """Attach attributes to the current span (no-op if there is none)."""
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


F = TypeVar("F", bound=Callable[..., Any])


def traced(span_name: str) -> Callable[[F], F]:
    """Decorator that runs the wrapped function inside a span named *span_name*.

    Use ``set_span_attributes`` inside the function to record phase metrics.
    Exceptions are recorded on the span and re-raised.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator
