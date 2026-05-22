"""Domain models for the chat feature.

Thin dataclasses used by the store and router — no ORM coupling here (ADR-011).
The DB schema lives in migration 0002.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class ChatSession:
    id: UUID
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime


@dataclass
class ChatMessage:
    id: int
    session_id: UUID
    turn_idx: int
    role: str  # 'user' | 'assistant'
    content: str
    citations: list[dict]
    created_at: datetime


@dataclass
class Citation:
    """A single citation emitted with the response."""

    source: str
    section: str
    chunk_hash: str = ""
    content: str = ""


@dataclass
class ChatTurn:
    """A resolved conversation turn for the rewriter (user query + assistant answer)."""

    question: str
    answer: str


@dataclass
class UsageMeta:
    """Token usage reported by the Gemini API for a single generation call."""

    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0
    cached_content_token_count: int = 0

    @classmethod
    def from_response_metadata(cls, meta: dict) -> "UsageMeta":
        usage = meta.get("usage_metadata", {}) if meta else {}
        return cls(
            prompt_token_count=usage.get("prompt_token_count", 0),
            candidates_token_count=usage.get("candidates_token_count", 0),
            total_token_count=usage.get("total_token_count", 0),
            cached_content_token_count=usage.get("cached_content_token_count", 0),
        )


@dataclass
class StreamEvent:
    """A single event emitted during SSE streaming."""

    type: str  # 'token' | 'citations' | 'error'
    content: str = ""
    items: list[dict] = field(default_factory=list)
    message: str = ""
