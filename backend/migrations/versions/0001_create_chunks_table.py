"""Create chunks table with HNSW and GIN indexes.

Revision ID: 0001
Revises: -
Create Date: 2026-05-21
Block: B (Corpus + Indexación)

Schema (spec 01):
  chunks(id, content, embedding vector(1536), metadata jsonb,
         content_tsv tsvector, corpus_sha, chunk_hash, indexed_at)

Indexes:
  - HNSW on embedding (vector_cosine_ops) for ANN search.
  - GIN on content_tsv for full-text (BM25-style) search.
  - UNIQUE on chunk_hash for idempotent upserts.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension exists (idempotent; init.sql also creates it).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id          BIGSERIAL PRIMARY KEY,
            content     TEXT         NOT NULL,
            embedding   VECTOR(1536) NOT NULL,
            metadata    JSONB        NOT NULL DEFAULT '{}',
            content_tsv TSVECTOR,
            corpus_sha  TEXT         NOT NULL,
            chunk_hash  TEXT         NOT NULL,
            indexed_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT chunks_chunk_hash_unique UNIQUE (chunk_hash)
        )
        """
    )

    # HNSW index for approximate nearest-neighbour search (cosine distance).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # GIN index for full-text search (tsvector column).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_content_tsv_gin
        ON chunks USING gin (content_tsv)
        """
    )

    # B-tree index on corpus_sha for fast corpus-scoped queries.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_corpus_sha_idx
        ON chunks (corpus_sha)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks CASCADE")
