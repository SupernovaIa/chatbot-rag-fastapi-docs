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
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.observability.tracing import traced
from app.retrieval.hybrid import PgVectorHybridSearcher
from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
from app.retrieval.models import Turn
from app.retrieval.orchestrator import retrieve

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


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


@router.post("/")
async def chat_endpoint(  # noqa: PLR0913
    body: ChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    store: ChatHistoryStore = Depends(get_store),
    searcher: PgVectorHybridSearcher = Depends(get_searcher),
    embeddings: QueryEmbeddingsAdapter = Depends(get_embeddings),
    rewrite_llm: GeminiChatAdapter = Depends(get_rewrite_llm),
    rerank_llm: GeminiChatAdapter = Depends(get_rerank_llm),
    current_user: User = Depends(current_active_user),
) -> EventSourceResponse:
    """Stream a RAG response for *body.query*.

    Pipeline: load history → rewrite → retrieve → rerank → build prompt →
    stream generation → persist turn.

    The retrieval phases run synchronously in a thread-pool executor so they
    don't block the event loop. The generation phase is fully async (astream).
    """
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

    # 3. Run retrieval pipeline in thread pool (sync functions)
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
    # The authoritative index is computed inside save_turn under an advisory lock.
    turn_idx_hint = await asyncio.to_thread(store.next_turn_idx, session_id)

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

    async def event_generator():
        # Stream tokens
        async for event in stream_chat(
            messages=messages,
            model=settings.gemini_flash_model,
            api_key=settings.google_api_key,
            timeout=settings.generate_timeout_s,
            disconnect_event=disconnect_event,
            session=gen_session,
        ):
            yield {"data": json.dumps(event)}

        if gen_session.cancelled:
            # Client disconnected or error — do not persist incomplete turn
            logger.debug(
                "Stream cancelled for session %s (hint turn %d) — skipping persistence",
                session_id,
                turn_idx_hint,
            )
            return

        # Emit citations as final event
        yield {"data": json.dumps({"type": "citations", "items": citations_payload})}

        # Persist the completed turn (sync → thread pool).
        # save_turn acquires an advisory lock and computes the authoritative turn_idx.
        turn_idx = await asyncio.to_thread(
            store.save_turn,
            session_id,
            body.query,
            gen_session.full_text,
            citations_payload,
        )

        # Record generation attributes in the log.
        # TODO(block-F): emit a proper OTel span here. event_generator() runs
        # outside the @traced context of the route handler (the handler returns
        # the EventSourceResponse before the generator is exhausted), so
        # set_span_attributes() would target a no-op span. Fix: start_span()
        # manually, pass it into stream_chat, end() it when the generator finishes.
        usage = gen_session.usage
        logger.debug(
            "Turn %d saved | session=%s prompt_tokens=%d cached_tokens=%s output_tokens=%d",
            turn_idx,
            session_id,
            usage.prompt_token_count,
            usage.cached_content_token_count,
            usage.candidates_token_count,
        )

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
