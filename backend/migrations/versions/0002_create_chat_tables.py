"""Create chat_sessions and chat_messages tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21
Block: CH (Backend de chat)

Schema (specs 05/06):
  chat_sessions(id UUID PK, user_id UUID nullable, created_at, updated_at)
  chat_messages(id bigserial PK, session_id, turn_idx, role, content, citations, created_at)

Unique constraint note: the task spec lists UNIQUE (session_id, turn_idx), but since
turn_idx represents a conversation round (user + assistant share the same round number),
the correct discriminant is (session_id, turn_idx, role). A strict (session_id, turn_idx)
unique would reject the assistant row for an existing user row of the same turn.
Decision: implement (session_id, turn_idx, role) and document the deviation.

Concurrency: UNIQUE on (session_id, turn_idx, role) doubles as the advisory lock for
concurrent turns — the DB rejects a duplicate insert instead of silently overwriting.
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chat_sessions: one row per conversation. user_id is nullable until the
    # auth block (AU) wires FastAPI Users; the FK will be added in migration 0003.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # chat_messages: two rows per turn (role='user' + role='assistant').
    # turn_idx is the 1-based round number within the session.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          BIGSERIAL   PRIMARY KEY,
            session_id  UUID        NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            turn_idx    INTEGER     NOT NULL CHECK (turn_idx >= 1),
            role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
            content     TEXT        NOT NULL,
            citations   JSONB       NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chat_messages_session_turn_role_unique UNIQUE (session_id, turn_idx, role)
        )
        """
    )

    # Index for fast history lookups ordered by turn_idx.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chat_messages_session_id_turn_idx_idx
        ON chat_messages (session_id, turn_idx)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_sessions CASCADE")
