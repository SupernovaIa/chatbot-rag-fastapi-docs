"""pgvector chunk store adapter.

Implements ChunkStorePort with an upsert-on-conflict strategy.
The idempotency key is ``chunk_hash`` (SHA-256 of content + corpus_sha).

Re-indexing the same corpus is safe: existing rows are skipped.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.indexing.models import Chunk
from app.indexing.ports import ChunkStorePort

logger = logging.getLogger(__name__)

_UPSERT_SQL = text(
    """
    INSERT INTO chunks (content, embedding, metadata, content_tsv, corpus_sha, chunk_hash, indexed_at)
    VALUES (
        :content,
        :embedding ::vector,
        :metadata ::jsonb,
        to_tsvector('english', :content),
        :corpus_sha,
        :chunk_hash,
        :indexed_at
    )
    ON CONFLICT (chunk_hash) DO NOTHING
    RETURNING id
    """
)

_COUNT_SQL = text("SELECT COUNT(*) FROM chunks")


class PgVectorChunkStore:
    """Persists chunks in Postgres with pgvector.

    Parameters
    ----------
    engine:
        SQLAlchemy engine pointing at the chatbot_rag database.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- ChunkStorePort ---

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        """Insert chunks, skipping duplicates.  Returns count of new rows."""
        if not chunks:
            return 0

        inserted = 0
        with self._engine.begin() as conn:
            for chunk in chunks:
                row = conn.execute(
                    _UPSERT_SQL,
                    {
                        "content": chunk.content,
                        "embedding": f"[{','.join(str(x) for x in chunk.embedding)}]",
                        "metadata": json.dumps(chunk.metadata),
                        "corpus_sha": chunk.corpus_sha,
                        "chunk_hash": chunk.chunk_hash,
                        "indexed_at": chunk.indexed_at,
                    },
                ).fetchone()
                if row is not None:
                    inserted += 1

        logger.info(
            "upsert_chunks: %d/%d new rows inserted",
            inserted,
            len(chunks),
        )
        return inserted

    def count(self) -> int:
        """Return total number of chunks in the table."""
        with self._engine.connect() as conn:
            result = conn.execute(_COUNT_SQL).scalar()
        return int(result or 0)


# Make the class satisfy the Protocol at type-check time.
_: ChunkStorePort = PgVectorChunkStore.__new__(PgVectorChunkStore)  # type: ignore[assignment]
