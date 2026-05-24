"""FastAPI router for the retrieval feature: ``POST /retrieve``.

Returns the reranked top-K candidates with their scores. Does not call the
generator (that lives in the chat feature). Dependencies are wired with
``Depends`` (ADR-011): a singleton engine + adapters built from settings.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import Settings, get_settings
from app.retrieval.hybrid import PgVectorHybridSearcher
from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
from app.retrieval.models import Turn
from app.retrieval.orchestrator import retrieve

router = APIRouter(tags=["retrieval"])


# --- Request / response schemas ---


class TurnIn(BaseModel):
    question: str
    answer: str


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    history: list[TurnIn] = Field(default_factory=list)
    top_k: int | None = None


class CandidateOut(BaseModel):
    chunk_hash: str
    source: str
    section: str
    content: str
    dense_rank: int | None
    sparse_rank: int | None
    rrf_score: float
    rerank_position: int | None


class RetrieveResponse(BaseModel):
    original_query: str
    rewritten_query: str
    rerank_fallback_used: bool
    candidates: list[CandidateOut]


# --- Dependency wiring (singletons keyed by settings) ---


@lru_cache(maxsize=1)
def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


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
        max_retries=settings.rerank_max_retries,  # fail fast → keep original query
    )


def get_rerank_llm(settings: Settings = Depends(get_settings)) -> GeminiChatAdapter:
    # Dedicated client with the rerank timeout; no SDK retries so a slow/5xx
    # call degrades to hybrid order fast instead of stalling on backoff.
    return GeminiChatAdapter(
        api_key=settings.google_api_key,
        model=settings.gemini_flash_model,
        timeout=settings.rerank_timeout_s,
        max_retries=settings.rerank_max_retries,
    )


# --- Route ---


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(
    request: RetrieveRequest,
    settings: Settings = Depends(get_settings),
    searcher: PgVectorHybridSearcher = Depends(get_searcher),
    embeddings: QueryEmbeddingsAdapter = Depends(get_embeddings),
    rewrite_llm: GeminiChatAdapter = Depends(get_rewrite_llm),
    rerank_llm: GeminiChatAdapter = Depends(get_rerank_llm),
) -> RetrieveResponse:
    """Run rewrite → hybrid search → rerank and return the top-K with scores."""
    history = [Turn(question=t.question, answer=t.answer) for t in request.history]
    result = retrieve(
        query=request.query,
        embeddings=embeddings,
        searcher=searcher,
        rewrite_llm=rewrite_llm,
        rerank_llm=rerank_llm,
        history=history,
        candidates=settings.retrieval_candidates,
        top_k=request.top_k or settings.retrieval_top_k,
    )
    return RetrieveResponse(
        original_query=result.original_query,
        rewritten_query=result.rewritten_query,
        rerank_fallback_used=result.rerank_fallback_used,
        candidates=[
            CandidateOut(
                chunk_hash=c.chunk_hash,
                source=c.source,
                section=c.section,
                content=c.content,
                dense_rank=c.dense_rank,
                sparse_rank=c.sparse_rank,
                rrf_score=c.rrf_score,
                rerank_position=c.rerank_position,
            )
            for c in result.candidates
        ],
    )
