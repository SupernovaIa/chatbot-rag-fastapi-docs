"""Chat history persistence: session + message CRUD.

All operations use the same synchronous SQLAlchemy Engine as the retrieval
feature. Callers that live in an async context must wrap calls with
``asyncio.to_thread`` (see router.py).

Concurrency — turn_idx serialisation
--------------------------------------
``save_turn`` acquires a session-scoped advisory lock (``pg_advisory_xact_lock``)
BEFORE reading ``MAX(turn_idx)`` and inserting. The lock is held for the duration
of the transaction and released automatically on commit/rollback. This prevents
two concurrent requests for the same session from computing the same next index
(TOCTOU gap closed). The UNIQUE constraint on (session_id, turn_idx, role) remains
as an additional last-resort guard.

``next_turn_idx`` is kept as a read-only helper (no lock) for callers that need
a best-effort estimate before the actual save (e.g. pre-streaming logging).
"""

from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.chat.models import ChatMessage, ChatSession, ChatTurn

logger = logging.getLogger(__name__)


class ChatHistoryStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def get_or_create_session(self, session_id: UUID | None, user_id: UUID | None = None) -> UUID:
        """Return existing session UUID or create a new one.

        If *session_id* is given but not found in the DB, a new session is
        created with the provided UUID (idempotent replay / client-side IDs).
        """
        sid = session_id or uuid4()
        with self._engine.begin() as conn:
            row = conn.execute(
                text("SELECT id FROM chat_sessions WHERE id = :id"),
                {"id": str(sid)},
            ).fetchone()
            if row is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO chat_sessions (id, user_id)
                        VALUES (:id, :user_id)
                        ON CONFLICT (id) DO NOTHING
                        """
                    ),
                    {"id": str(sid), "user_id": str(user_id) if user_id else None},
                )
        return sid

    def get_session(self, session_id: UUID) -> ChatSession | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, user_id, created_at, updated_at "
                    "FROM chat_sessions WHERE id = :id"
                ),
                {"id": str(session_id)},
            ).fetchone()
        if row is None:
            return None
        return ChatSession(
            id=UUID(str(row[0])),
            user_id=UUID(str(row[1])) if row[1] else None,
            created_at=row[2],
            updated_at=row[3],
        )

    def list_sessions(self, user_id: UUID | None = None, limit: int = 50) -> list[ChatSession]:
        with self._engine.connect() as conn:
            if user_id is not None:
                query = (
                    "SELECT id, user_id, created_at, updated_at "
                    "FROM chat_sessions WHERE user_id = :uid ORDER BY updated_at DESC LIMIT :limit"
                )
                params = {"uid": str(user_id), "limit": limit}
            else:
                query = (
                    "SELECT id, user_id, created_at, updated_at "
                    "FROM chat_sessions ORDER BY updated_at DESC LIMIT :limit"
                )
                params = {"limit": limit}
            rows = conn.execute(text(query), params).fetchall()
        return [
            ChatSession(
                id=UUID(str(r[0])),
                user_id=UUID(str(r[1])) if r[1] else None,
                created_at=r[2],
                updated_at=r[3],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def load_history(self, session_id: UUID, window: int = 5) -> list[ChatTurn]:
        """Return the last *window* complete turns (user + assistant pairs).

        Ordered oldest-first so the rewriter and prompt builder see chronological
        context. Incomplete turns (assistant message not yet written) are skipped.
        """
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    WITH ranked AS (
                        SELECT turn_idx
                        FROM chat_messages
                        WHERE session_id = :sid
                        GROUP BY turn_idx
                        HAVING COUNT(DISTINCT role) = 2  -- only complete turns
                        ORDER BY turn_idx DESC
                        LIMIT :window
                    )
                    SELECT m.turn_idx, m.role, m.content
                    FROM chat_messages m
                    JOIN ranked r ON m.turn_idx = r.turn_idx
                    WHERE m.session_id = :sid
                    ORDER BY m.turn_idx ASC, m.role DESC  -- user before assistant
                    """
                ),
                {"sid": str(session_id), "window": window},
            ).fetchall()

        # Group by turn_idx
        turns: dict[int, dict[str, str]] = {}
        for turn_idx, role, content in rows:
            turns.setdefault(turn_idx, {})[role] = content

        return [
            ChatTurn(question=t["user"], answer=t["assistant"])
            for t in turns.values()
            if "user" in t and "assistant" in t
        ]

    def get_session_messages(self, session_id: UUID) -> list[ChatMessage]:
        """Full message history for a session (for the GET /chat/sessions/{id} endpoint)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, session_id, turn_idx, role, content, citations, created_at "
                    "FROM chat_messages WHERE session_id = :sid "
                    "ORDER BY turn_idx ASC, role DESC"
                ),
                {"sid": str(session_id)},
            ).fetchall()
        return [
            ChatMessage(
                id=r[0],
                session_id=UUID(str(r[1])),
                turn_idx=r[2],
                role=r[3],
                content=r[4],
                citations=r[5] if isinstance(r[5], list) else json.loads(r[5] or "[]"),
                created_at=r[6],
            )
            for r in rows
        ]

    def next_turn_idx(self, session_id: UUID) -> int:
        """Best-effort estimate of the next turn_idx (no lock, read-only).

        Suitable for pre-streaming logging. The authoritative index is computed
        inside ``save_turn`` under an advisory lock.
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(MAX(turn_idx), 0) + 1 "
                    "FROM chat_messages WHERE session_id = :sid"
                ),
                {"sid": str(session_id)},
            ).fetchone()
        return row[0] if row else 1

    def save_turn(
        self,
        session_id: UUID,
        query: str,
        answer: str,
        citations: list[dict],
    ) -> int:
        """Insert the user and assistant rows for a completed turn.

        Acquires a session-scoped advisory lock before computing ``turn_idx`` so
        that concurrent requests on the same session are serialised. The lock is
        released automatically when the transaction commits or rolls back.

        Returns the turn_idx that was written.
        """
        citations_json = json.dumps(citations)
        with self._engine.begin() as conn:
            # Serialise concurrent saves on the same session.
            # hashtext() maps the UUID string to a 32-bit int for pg_advisory_xact_lock.
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:sid))"),
                {"sid": str(session_id)},
            )
            # Read MAX(turn_idx) inside the lock — safe from TOCTOU.
            row = conn.execute(
                text(
                    "SELECT COALESCE(MAX(turn_idx), 0) + 1 "
                    "FROM chat_messages WHERE session_id = :sid"
                ),
                {"sid": str(session_id)},
            ).fetchone()
            turn_idx = row[0] if row else 1

            conn.execute(
                text(
                    """
                    INSERT INTO chat_messages (session_id, turn_idx, role, content, citations)
                    VALUES (:sid, :turn, 'user', :content, '[]'::jsonb)
                    ON CONFLICT (session_id, turn_idx, role) DO NOTHING
                    """
                ),
                {"sid": str(session_id), "turn": turn_idx, "content": query},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO chat_messages (session_id, turn_idx, role, content, citations)
                    VALUES (:sid, :turn, 'assistant', :content, :citations::jsonb)
                    ON CONFLICT (session_id, turn_idx, role) DO NOTHING
                    """
                ),
                {
                    "sid": str(session_id),
                    "turn": turn_idx,
                    "content": answer,
                    "citations": citations_json,
                },
            )
            conn.execute(
                text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :sid"),
                {"sid": str(session_id)},
            )
        logger.debug("Saved turn %d for session %s", turn_idx, session_id)
        return turn_idx
