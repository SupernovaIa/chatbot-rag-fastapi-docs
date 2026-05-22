"""Shared fakes and fixtures for chat unit tests (no network, no DB)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.chat.models import ChatMessage, ChatSession, ChatTurn
from app.retrieval.models import Candidate


# ---------------------------------------------------------------------------
# Fake DB engine
# ---------------------------------------------------------------------------


class FakeConn:
    """Fake SQLAlchemy connection with pre-programmed query responses."""

    def __init__(self, responses: dict[str, object]) -> None:
        """*responses* maps a substring of the SQL to a return value."""
        self._responses = responses
        self.executed: list[str] = []

    def execute(self, stmt, params=None):  # noqa: ANN001
        sql = str(stmt)
        self.executed.append(sql)
        for key, val in self._responses.items():
            if key.lower() in sql.lower():
                return _FakeResult(val if isinstance(val, list) else [val])
        return _FakeResult([])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class FakeEngine:
    """Fake SQLAlchemy engine whose connect/begin yield a FakeConn."""

    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self._responses: dict[str, object] = responses or {}
        self.conn: FakeConn = FakeConn(self._responses)

    @contextmanager
    def connect(self):
        yield self.conn

    @contextmanager
    def begin(self):
        yield self.conn


# ---------------------------------------------------------------------------
# Fake store
# ---------------------------------------------------------------------------


class FakeChatHistoryStore:
    """In-memory implementation of the ChatHistoryStore interface."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, ChatSession] = {}
        self._messages: list[ChatMessage] = []
        self.saved_turns: list[dict] = []

    def get_or_create_session(self, session_id: UUID | None = None, user_id: UUID | None = None) -> UUID:
        sid = session_id or uuid4()
        if sid not in self._sessions:
            now = datetime.now(tz=timezone.utc)
            self._sessions[sid] = ChatSession(
                id=sid, user_id=user_id, created_at=now, updated_at=now
            )
        return sid

    def get_session(self, session_id: UUID) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, user_id: UUID | None = None, limit: int = 50) -> list[ChatSession]:
        sessions = self._sessions.values()
        if user_id is not None:
            sessions = (s for s in sessions if s.user_id == user_id)
        return list(sessions)[:limit]

    def load_history(self, session_id: UUID, window: int = 5) -> list[ChatTurn]:
        turns: dict[int, dict] = {}
        for m in self._messages:
            if m.session_id == session_id:
                turns.setdefault(m.turn_idx, {})[m.role] = m.content
        complete = [
            (idx, t) for idx, t in sorted(turns.items()) if "user" in t and "assistant" in t
        ]
        # Sliding window: last *window* complete turns
        return [ChatTurn(question=t["user"], answer=t["assistant"]) for _, t in complete[-window:]]

    def get_session_messages(self, session_id: UUID) -> list[ChatMessage]:
        return [m for m in self._messages if m.session_id == session_id]

    def next_turn_idx(self, session_id: UUID) -> int:
        turns = [m.turn_idx for m in self._messages if m.session_id == session_id]
        return max(turns, default=0) + 1

    def save_turn(
        self,
        session_id: UUID,
        query: str,
        answer: str,
        citations: list[dict],
    ) -> int:
        """Mirror of the real store: computes turn_idx internally, returns it."""
        turn_idx = self.next_turn_idx(session_id)
        now = datetime.now(tz=timezone.utc)
        self._messages.append(
            ChatMessage(
                id=len(self._messages) + 1,
                session_id=session_id,
                turn_idx=turn_idx,
                role="user",
                content=query,
                citations=[],
                created_at=now,
            )
        )
        self._messages.append(
            ChatMessage(
                id=len(self._messages) + 1,
                session_id=session_id,
                turn_idx=turn_idx,
                role="assistant",
                content=answer,
                citations=citations,
                created_at=now,
            )
        )
        self.saved_turns.append(
            {
                "session_id": session_id,
                "turn_idx": turn_idx,
                "query": query,
                "answer": answer,
                "citations": citations,
            }
        )
        return turn_idx


# ---------------------------------------------------------------------------
# Fake retrieval
# ---------------------------------------------------------------------------


def make_candidate(cid: str = "abc", **kwargs) -> Candidate:
    return Candidate(
        chunk_hash=cid,
        content=kwargs.get("content", f"content of {cid}"),
        source=kwargs.get("source", f"{cid}.md"),
        section=kwargs.get("section", "Overview"),
        rrf_score=kwargs.get("rrf_score", 0.5),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_store() -> FakeChatHistoryStore:
    return FakeChatHistoryStore()


@pytest.fixture
def sample_candidates() -> list[Candidate]:
    return [
        make_candidate("h1", source="tutorial/path-params.md", section="Path Parameters"),
        make_candidate("h2", source="tutorial/query-params.md", section="Query Parameters"),
    ]
