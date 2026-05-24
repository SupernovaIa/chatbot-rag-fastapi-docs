"""FastAPI router for the chat feature.

Routes
------
POST /chat
    Orchestrates: load history → rewrite → retrieve → rerank → build prompt →
    stream generation → persist turn. Returns an SSE stream with token/citations
    events (spec 05). Cancels the LLM call on client disconnect (free-tier safety).

GET /chat/sessions
    Lists all sessions (no auth yet — added in block AU).

GET /chat/sessions/{session_id}
    Full message history for a session.

Dependency graph (ADR-011)
--------------------------
Settings → Engine (singleton) → ChatHistoryStore
Settings → PgVectorHybridSearcher
Settings → QueryEmbeddingsAdapter
Settings → GeminiChatAdapter (rewrite)
Settings → GeminiChatAdapter (rerank)

All retrieval adapters are reused from the retrieval router to avoid
constructing duplicate clients on each request.

Span hierarchy (block F, ADR-008)
----------------------------------
chat_turn  (manual span, starts before retrieval, ends after generate)
├── chat_retrieve  (@traced wrapper)
│   └── retrieve   (@traced orchestrator)
│       ├── rewrite       (@traced)
│       ├── hybrid_search (@traced, via PgVectorHybridSearcher.search)
│       └── rerank        (@traced)
└── generate  (manual span, started/ended inside event_generator)
    └── ChatGoogleGenerativeAI  (auto-instrumented by LangChainInstrumentor)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.trace import set_span_in_context
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sse_starlette.sse import EventSourceResponse

from app.auth.models import User
from app.auth.router import current_active_user
from app.chat.generator import StreamingSession, stream_chat
from app.chat.models import Citation
from app.chat.prompts import build_prompt, citations_from_candidates
from app.chat.store import ChatHistoryStore
from app.config import Settings, get_settings
from app.observability.cost import compute_cost
from app.observability.tracing import get_tracer, traced
from app.retrieval.hybrid import PgVectorHybridSearcher
from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
from app.retrieval.models import Turn
from app.retrieval.orchestrator import retrieve
from app.security.guardrail import InputGuardrail
from app.security.incidents import SAFE_RESPONSE, log_incident
from app.security.models import BlockingLayer
from app.security.output_filter import StreamRedactor, detect_system_prompt_leak
from app.security.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    session_id: UUID | None = Field(
        default=None,
        description="Existing session UUID. Omit to start a new session.",
    )


class SessionOut(BaseModel):
    id: UUID
    created_at: str
    updated_at: str
    message_count: int = 0


class MessageOut(BaseModel):
    turn_idx: int
    role: str
    content: str
    citations: list[dict]
    created_at: str


class SessionDetailOut(BaseModel):
    id: UUID
    created_at: str
    updated_at: str
    messages: list[MessageOut]


# ---------------------------------------------------------------------------
# Singleton infrastructure (shared with retrieval router)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def get_store(settings: Settings = Depends(get_settings)) -> ChatHistoryStore:
    engine = _get_engine(settings.database_url)
    return ChatHistoryStore(engine)


def get_searcher(settings: Settings = Depends(get_settings)) -> PgVectorHybridSearcher:
    engine = _get_engine(settings.database_url)
    return PgVectorHybridSearcher(
        engine=engine,
        corpus_sha=settings.corpus_sha,
        rrf_k=settings.rrf_k,
    )


def get_embeddings(settings: Settings = Depends(get_settings)) -> QueryEmbeddingsAdapter:
    return QueryEmbeddingsAdapter(api_key=settings.google_api_key)


def get_rewrite_llm(settings: Settings = Depends(get_settings)) -> GeminiChatAdapter:
    return GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.rewrite_timeout_s,
    )


def get_rerank_llm(settings: Settings = Depends(get_settings)) -> GeminiChatAdapter:
    return GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.rerank_timeout_s,
    )


def get_guardrail(settings: Settings = Depends(get_settings)) -> InputGuardrail:
    """Layer-2 guardrail backed by a Flash adapter (fail-fast, no SDK retries)."""
    # NB: do not pass max_retries here — that kwarg makes langchain build the
    # Gemini client eagerly, which would turn an unauthenticated request into a
    # 500 (no key) instead of a clean 401. The guardrail fails open on any error
    # (incl. timeout), so the fast-fail behaviour is preserved regardless.
    adapter = GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.guardrail_timeout_s,
    )
    return InputGuardrail(adapter)


async def rate_limited_user(
    current_user: User = Depends(current_active_user),
) -> User:
    """Authenticate, then enforce the layer-5 per-user rate limit.

    Runs after ``current_active_user`` so an unauthenticated request still gets
    a clean 401. On exceed, logs a layer-5 incident and raises HTTP 429.
    """
    if not check_rate_limit(str(current_user.id)):
        log_incident(
            layer=BlockingLayer.RATE_LIMIT,
            blocked=True,
            query="",
            user_id=str(current_user.id),
            reason="per-user rate limit exceeded",
        )
        raise HTTPException(
            status_code=429,
            detail=SAFE_RESPONSE,
            headers={"Retry-After": "60"},
        )
    return current_user


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


def _safe_response(message: str = SAFE_RESPONSE) -> EventSourceResponse:
    """Return an SSE stream carrying a single safe message + empty citations.

    Used when a security layer blocks the request: the client sees a normal
    (but refusing) answer, with no partial/hostile content and no leak.
    """

    async def _gen():
        yield {"data": json.dumps({"type": "token", "content": message})}
        yield {"data": json.dumps({"type": "citations", "items": []})}

    return EventSourceResponse(_gen())


@router.post("/")
async def chat_endpoint(  # noqa: PLR0913
    body: ChatRequest,
    request: Request,
    # current_user (auth + layer-5 rate limit) is declared FIRST so it resolves
    # before the Gemini-adapter dependencies. Those construct their client
    # eagerly and would raise (turning a missing-auth request into a 500) if
    # they resolved before authentication; FastAPI resolves Depends params in
    # declaration order, so auth must come first to win with a clean 401/429.
    current_user: User = Depends(rate_limited_user),
    settings: Settings = Depends(get_settings),
    store: ChatHistoryStore = Depends(get_store),
    searcher: PgVectorHybridSearcher = Depends(get_searcher),
    embeddings: QueryEmbeddingsAdapter = Depends(get_embeddings),
    rewrite_llm: GeminiChatAdapter = Depends(get_rewrite_llm),
    rerank_llm: GeminiChatAdapter = Depends(get_rerank_llm),
    guardrail: InputGuardrail = Depends(get_guardrail),
) -> EventSourceResponse:
    """Stream a RAG response for *body.query*.

    Pipeline: load history → rewrite → retrieve → rerank → build prompt →
    stream generation → persist turn.

    The retrieval phases run synchronously in a thread-pool executor so they
    don't block the event loop. The generation phase is fully async (astream).

    Span hierarchy emitted (block F):
      chat_turn → chat_retrieve → retrieve → {rewrite, hybrid_search, rerank}
               └→ generate (manual) → ChatGoogleGenerativeAI (auto-instrumented)
    """
    # ------------------------------------------------------------------ #
    # 0. Start chat_turn span (manual — must outlive the route handler)   #
    # ------------------------------------------------------------------ #
    tracer = get_tracer()
    chat_start = time.perf_counter()

    # start_span does NOT set it as current; we attach it manually so that
    # asyncio.to_thread calls (retrieval) inherit the context.
    chat_turn_span = tracer.start_span(
        "chat_turn",
        attributes={
            "session_id": str(body.session_id or ""),
            "query_len": len(body.query),
            "user_id": str(current_user.id),
            "model": settings.gemini_flash_model,
        },
    )
    _ctx_token = otel_context.attach(set_span_in_context(chat_turn_span))

    # Track the layer-2 guardrail verdict so suspicious turns can be flagged on
    # the span / incident even though they are still answered.
    guardrail_flagged = False

    try:
        # ------------------------------------------------------------------ #
        # Layer 2: input guardrail. Runs before any retrieval/generation so a #
        # hostile prompt never reaches the model or the corpus.               #
        # ------------------------------------------------------------------ #
        if settings.security_guardrail_enabled:
            verdict = await asyncio.to_thread(guardrail.classify, body.query)
            chat_turn_span.set_attribute("guardrail_verdict", verdict.verdict.value)
            if verdict.failed_open:
                chat_turn_span.set_attribute("guardrail_failed_open", True)
            if verdict.blocked:
                chat_turn_span.set_attribute("blocking_layer", int(BlockingLayer.GUARDRAIL))
                log_incident(
                    layer=BlockingLayer.GUARDRAIL,
                    blocked=True,
                    query=body.query,
                    user_id=str(current_user.id),
                    session_id=str(body.session_id or ""),
                    reason=verdict.reason or "hostile input",
                )
                chat_turn_span.set_attribute("blocked", True)
                chat_turn_span.end()
                return _safe_response()
            if verdict.flagged:
                guardrail_flagged = True
                log_incident(
                    layer=BlockingLayer.GUARDRAIL,
                    blocked=False,
                    query=body.query,
                    user_id=str(current_user.id),
                    session_id=str(body.session_id or ""),
                    reason=verdict.reason or "suspicious input",
                )

        # 1. Resolve / create session
        session_id = await asyncio.to_thread(
            store.get_or_create_session, body.session_id, current_user.id
        )

        # 2. Load history (sliding window N=5)
        history_turns = await asyncio.to_thread(
            store.load_history, session_id, settings.history_window_n
        )
        # Convert ChatTurn → retrieval.Turn (same shape, different dataclass)
        history = [Turn(question=t.question, answer=t.answer) for t in history_turns]

        # 3. Run retrieval pipeline in thread pool (sync functions).
        #    asyncio.to_thread copies the current context (including chat_turn_span
        #    as current) so child spans are properly nested under chat_turn.
        @traced("chat_retrieve")
        def _run_retrieve() -> object:
            return retrieve(
                query=body.query,
                embeddings=embeddings,
                searcher=searcher,
                rewrite_llm=rewrite_llm,
                rerank_llm=rerank_llm,
                history=history,
                candidates=settings.retrieval_candidates,
                top_k=settings.retrieval_top_k,
            )

        retrieval_result = await asyncio.to_thread(_run_retrieve)

        # 4. Prepare citations and prompt
        citations: list[Citation] = citations_from_candidates(retrieval_result.candidates)
        messages = build_prompt(
            query=body.query,
            history=history,
            candidates=retrieval_result.candidates,
        )

        # 5. Best-effort turn_idx estimate for pre-streaming logging.
        turn_idx_hint = await asyncio.to_thread(store.next_turn_idx, session_id)

    except Exception as exc:
        # Retrieval phase failed before the generator was created.
        # End the span here — event_generator's finally will never run.
        chat_turn_span.record_exception(exc)
        chat_turn_span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR, str(exc)))
        chat_turn_span.end()
        raise

    finally:
        # Detach chat_turn_span from the current async task context regardless
        # of success or failure. The generator re-attaches it as parent context
        # for the generate span via set_span_in_context.
        otel_context.detach(_ctx_token)

    # 6. Set up disconnect detection
    disconnect_event = asyncio.Event()

    async def _watch_disconnect() -> None:
        while not disconnect_event.is_set():
            if await request.is_disconnected():
                disconnect_event.set()
                return
            await asyncio.sleep(0.25)

    asyncio.create_task(_watch_disconnect())

    # 7. Build SSE generator
    gen_session = StreamingSession()
    citations_payload = [
        {
            "source": c.source,
            "section": c.section,
            "chunk_hash": c.chunk_hash,
            "content": c.content,
        }
        for c in citations
    ]

    # Capture values for the generator closure
    _session_id = session_id
    _turn_idx_hint = turn_idx_hint
    _model = settings.gemini_flash_model

    async def event_generator():
        # ---------------------------------------------------------- #
        # Start generate span as child of chat_turn_span             #
        # ---------------------------------------------------------- #
        # Include session_id so the caching measurement script can filter
        # generate spans by session without having to inspect the parent.
        generate_span = tracer.start_span(
            "generate",
            context=set_span_in_context(chat_turn_span),
            attributes={
                "model": _model,
                "session_id": str(_session_id),
            },
        )
        stream_start = time.perf_counter()
        ttft_ms: float | None = None

        # Layer 4: redact PII from the token stream as it flows (holds back an
        # in-flight tail so a forming pattern is never emitted un-redacted).
        redactor = StreamRedactor()

        try:
            # Stream tokens
            async for event in stream_chat(
                messages=messages,
                model=_model,
                api_key=settings.google_api_key,
                timeout=settings.generate_timeout_s,
                disconnect_event=disconnect_event,
                session=gen_session,
            ):
                # Record TTFT on the first token event
                if ttft_ms is None and isinstance(event, dict) and event.get("type") == "token":
                    ttft_ms = (time.perf_counter() - stream_start) * 1000.0

                # Pass token content through the layer-4 redactor; forward other
                # event types (error) unchanged.
                if isinstance(event, dict) and event.get("type") == "token":
                    safe = redactor.feed(event.get("content", ""))
                    if safe:
                        yield {"data": json.dumps({"type": "token", "content": safe})}
                else:
                    yield {"data": json.dumps(event)}

            # ---------------------------------------------------------- #
            # Layer 1: Gemini safety filter blocked the generation.       #
            # ---------------------------------------------------------- #
            if gen_session.safety_blocked:
                generate_span.set_attribute("safety_blocked", True)
                generate_span.set_attribute("finish_reason", gen_session.finish_reason or "")
                chat_turn_span.set_attribute("blocking_layer", int(BlockingLayer.SAFETY_FILTER))
                chat_turn_span.set_attribute("blocked", True)
                log_incident(
                    layer=BlockingLayer.SAFETY_FILTER,
                    blocked=True,
                    query=body.query,
                    user_id=str(current_user.id),
                    session_id=str(_session_id),
                    reason=f"gemini safety finish_reason={gen_session.finish_reason}",
                )
                yield {"data": json.dumps({"type": "token", "content": SAFE_RESPONSE})}
                yield {"data": json.dumps({"type": "citations", "items": []})}
                return

            # Flush the redactor tail before emitting citations.
            tail = redactor.flush()
            if tail:
                yield {"data": json.dumps({"type": "token", "content": tail})}

            if gen_session.cancelled:
                logger.debug(
                    "Stream cancelled for session %s (hint turn %d) — skipping persistence",
                    _session_id,
                    _turn_idx_hint,
                )
                # Record what we know: flag + partial TTFT + partial latency.
                # Token counts and cost are not available (generation interrupted).
                generate_span.set_attribute("cancelled", True)
                if ttft_ms is not None:
                    generate_span.set_attribute("ttft_ms", round(ttft_ms, 1))
                partial_latency_ms = (time.perf_counter() - chat_start) * 1000.0
                chat_turn_span.set_attribute("cancelled", True)
                chat_turn_span.set_attribute("total_latency_ms", round(partial_latency_ms, 1))
                return

            # Emit citations as final event
            yield {"data": json.dumps({"type": "citations", "items": citations_payload})}

            # ---------------------------------------------------- #
            # Layer 4: post-stream audit on the redacted answer.    #
            # PII was already redacted inline; here we record the   #
            # counts and run the system-prompt-leak detector.       #
            # ---------------------------------------------------- #
            safe_text = redactor.redacted_text
            if redactor.pii_found:
                generate_span.set_attribute("pii_redacted", True)
                for cat, n in redactor.counts.items():
                    generate_span.set_attribute(f"pii_redacted.{cat}", n)
                log_incident(
                    layer=BlockingLayer.OUTPUT_FILTER,
                    blocked=False,
                    query=body.query,
                    user_id=str(current_user.id),
                    session_id=str(_session_id),
                    reason="pii redacted from output",
                    detail=dict(redactor.counts),
                )
            if detect_system_prompt_leak(safe_text):
                generate_span.set_attribute("system_prompt_leak", True)
                chat_turn_span.set_attribute("blocking_layer", int(BlockingLayer.OUTPUT_FILTER))
                log_incident(
                    layer=BlockingLayer.OUTPUT_FILTER,
                    blocked=False,
                    query=body.query,
                    user_id=str(current_user.id),
                    session_id=str(_session_id),
                    reason="system prompt leak detected in output",
                )
            if guardrail_flagged:
                chat_turn_span.set_attribute("guardrail_flagged", True)

            # Persist the completed turn (sync → thread pool). We store the
            # redacted text so PII is never written to the history DB.
            turn_idx = await asyncio.to_thread(
                store.save_turn,
                _session_id,
                body.query,
                safe_text,
                citations_payload,
            )

            # ---------------------------------------------------- #
            # Record generate span attributes (tokens + cost)       #
            # ---------------------------------------------------- #
            usage = gen_session.usage
            cost = compute_cost(usage, _model)

            generate_span.set_attribute("prompt_tokens", usage.prompt_token_count)
            generate_span.set_attribute("cached_tokens", usage.cached_content_token_count)
            generate_span.set_attribute("output_tokens", usage.candidates_token_count)
            generate_span.set_attribute("total_tokens", usage.total_token_count)
            generate_span.set_attribute("ttft_ms", round(ttft_ms or 0.0, 1))
            generate_span.set_attribute("caching_available", cost.caching_available)
            generate_span.set_attribute("cache_hit_rate", round(cost.cache_hit_rate, 4))
            generate_span.set_attribute("cost_usd", round(cost.total_usd, 8))
            generate_span.set_attribute("input_usd", round(cost.input_usd, 8))
            generate_span.set_attribute("cached_usd", round(cost.cached_usd, 8))
            generate_span.set_attribute("output_usd", round(cost.output_usd, 8))
            generate_span.set_attribute("savings_usd", round(cost.savings_usd, 8))

            # ---------------------------------------------------- #
            # Record chat_turn span attributes (aggregate)          #
            # ---------------------------------------------------- #
            total_latency_ms = (time.perf_counter() - chat_start) * 1000.0
            chat_turn_span.set_attribute("turn_idx", turn_idx)
            chat_turn_span.set_attribute("total_latency_ms", round(total_latency_ms, 1))
            chat_turn_span.set_attribute("total_cost_usd", round(cost.total_usd, 8))
            chat_turn_span.set_attribute("prompt_tokens", usage.prompt_token_count)
            chat_turn_span.set_attribute("cached_tokens", usage.cached_content_token_count)
            chat_turn_span.set_attribute("output_tokens", usage.candidates_token_count)

            logger.debug(
                "Turn %d saved | session=%s prompt_tokens=%d cached_tokens=%s "
                "output_tokens=%d ttft_ms=%.1f cost_usd=%.6f caching=%s",
                turn_idx,
                _session_id,
                usage.prompt_token_count,
                usage.cached_content_token_count,
                usage.candidates_token_count,
                ttft_ms or 0.0,
                cost.total_usd,
                cost.caching_available,
            )

        except Exception as exc:
            generate_span.record_exception(exc)
            generate_span.set_status(
                otel_trace.Status(otel_trace.StatusCode.ERROR, str(exc))
            )
            chat_turn_span.record_exception(exc)
            chat_turn_span.set_status(
                otel_trace.Status(otel_trace.StatusCode.ERROR, str(exc))
            )
            raise

        finally:
            generate_span.end()
            chat_turn_span.end()

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /chat/sessions
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(
    store: ChatHistoryStore = Depends(get_store),
    current_user: User = Depends(current_active_user),
) -> list[SessionOut]:
    """List chat sessions for the authenticated user."""
    sessions = await asyncio.to_thread(store.list_sessions, current_user.id)
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# GET /chat/sessions/{session_id}
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    store: ChatHistoryStore = Depends(get_store),
    current_user: User = Depends(current_active_user),
) -> SessionDetailOut:
    """Full message history for a session (authenticated user must own it)."""
    session = await asyncio.to_thread(store.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    messages = await asyncio.to_thread(store.get_session_messages, session_id)
    return SessionDetailOut(
        id=session.id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        messages=[
            MessageOut(
                turn_idx=m.turn_idx,
                role=m.role,
                content=m.content,
                citations=m.citations,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )
