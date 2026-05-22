"""Create users table and add FK from chat_sessions.user_id to users.id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-22
Block: AU (Authentication)
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(320) NOT NULL,
            hashed_password VARCHAR(1024) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    op.execute(
        """
        ALTER TABLE chat_sessions
            ADD CONSTRAINT fk_chat_sessions_user_id
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE chat_sessions DROP CONSTRAINT fk_chat_sessions_user_id"
    )
    op.execute("DROP TABLE users CASCADE")
