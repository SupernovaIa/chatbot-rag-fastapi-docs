"""pgvector chunk store adapter.

Implements ChunkStorePort with an upsert-on-conflict strategy.
The idempotency key is ``chunk_hash`` (SHA-256 of content + corpus_sha).

Re-indexing the same corpus is safe: existing rows are skipped via
ON CONFLICT DO NOTHING.

Performance: chunks are inserted in batches of _INSERT_BATCH_SIZE rows
using SQLAlchemy executemany, reducing DB round-trips from O(n) to
O(n / batch_size).  The count of newly inserted rows is derived from
count_by_sha before vs. after the batch, avoiding RETURNING row-by-row.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.indexing.models import Chunk
from app.indexing.ports import ChunkStorePort

logger = logging.getLogger(__name__)

# Rows per executemany call.  500 is a safe default for Postgres;
# raise to 1000 if the embedding strings cause parameter size issues.
_INSERT_BATCH_SIZE = 500

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
    """
)

_COUNT_SQL = text("SELECT COUNT(*) FROM chunks")
_COUNT_BY_SHA_SQL = text("SELECT COUNT(*) FROM chunks WHERE corpus_sha = :corpus_sha")


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
        """Insert chunks in batches, skipping duplicates.

        Returns the count of new rows inserted (derived from count_by_sha
        delta rather than RETURNING, which is incompatible with executemany).
        """
        if not chunks:
            return 0

        corpus_sha = chunks[0].corpus_sha
        before = self.count_by_sha(corpus_sha)

        params = [
            {
                "content": c.content,
                "embedding": f"[{','.join(str(x) for x in c.embedding)}]",
                "metadata": json.dumps(c.metadata),
                "corpus_sha": c.corpus_sha,
                "chunk_hash": c.chunk_hash,
                "indexed_at": c.indexed_at,
            }
            for c in chunks
        ]

        with self._engine.begin() as conn:
            for i in range(0, len(params), _INSERT_BATCH_SIZE):
                batch = params[i : i + _INSERT_BATCH_SIZE]
                conn.execute(_UPSERT_SQL, batch)

        inserted = max(0, self.count_by_sha(corpus_sha) - before)
        logger.info(
            "upsert_chunks: %d/%d new rows inserted (corpus_sha=%s)",
            inserted,
            len(chunks),
            corpus_sha,
        )
        return inserted

    def count(self) -> int:
        """Return total number of chunks across all corpora."""
        with self._engine.connect() as conn:
            result = conn.execute(_COUNT_SQL).scalar()
        return int(result or 0)

    def count_by_sha(self, corpus_sha: str) -> int:
        """Return the number of chunks for a specific corpus SHA."""
        with self._engine.connect() as conn:
            result = conn.execute(
                _COUNT_BY_SHA_SQL, {"corpus_sha": corpus_sha}
            ).scalar()
        return int(result or 0)


# Make the class satisfy the Protocol at type-check time.
_: ChunkStorePort = PgVectorChunkStore.__new__(PgVectorChunkStore)  # type: ignore[assignment]
