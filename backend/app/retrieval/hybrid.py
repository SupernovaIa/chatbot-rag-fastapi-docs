"""Hybrid search: dense (cosine) + sparse (BM25-style tsvector) with RRF.

Spec 02. A single SQL query against pgvector runs both rankings and fuses them
with Reciprocal Rank Fusion::

    score = w_dense * 1/(k + rank_dense) + w_sparse * 1/(k + rank_sparse)

Distance: cosine (``<=>``) for consistency with the embedding docs (spec 02
open question). Sparse ranking uses ``ts_rank_cd`` over the GIN-indexed
``content_tsv`` column. Both legs are scoped to a single ``corpus_sha``.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.observability.tracing import set_span_attributes, traced
from app.retrieval.models import Candidate
from app.retrieval.ports import HybridSearchPort

logger = logging.getLogger(__name__)

# Single-query hybrid search with RRF fusion. Dense and sparse CTEs each return
# their own rank; a FULL OUTER JOIN unions the candidate sets so a chunk found
# by only one leg still scores.
_HYBRID_SQL = text(
    """
    WITH dense AS (
        SELECT chunk_hash, content, metadata,
               ROW_NUMBER() OVER (ORDER BY embedding <=> (:qvec)::vector) AS rank
        FROM chunks
        WHERE corpus_sha = :corpus_sha
        ORDER BY embedding <=> (:qvec)::vector
        LIMIT :candidates
    ),
    sparse AS (
        SELECT chunk_hash, content, metadata,
               ROW_NUMBER() OVER (ORDER BY ts_rank_cd(content_tsv, q) DESC) AS rank
        FROM chunks, plainto_tsquery('english', :query_text) AS q
        WHERE corpus_sha = :corpus_sha AND content_tsv @@ q
        ORDER BY ts_rank_cd(content_tsv, q) DESC
        LIMIT :candidates
    ),
    combined AS (
        SELECT
            COALESCE(d.chunk_hash, s.chunk_hash) AS chunk_hash,
            COALESCE(d.content, s.content)       AS content,
            COALESCE(d.metadata, s.metadata)     AS metadata,
            d.rank AS dense_rank,
            s.rank AS sparse_rank,
            :w_dense * COALESCE(1.0 / (:k + d.rank), 0.0)
              + :w_sparse * COALESCE(1.0 / (:k + s.rank), 0.0) AS rrf_score
        FROM dense d
        FULL OUTER JOIN sparse s ON d.chunk_hash = s.chunk_hash
    )
    SELECT chunk_hash, content, metadata, dense_rank, sparse_rank, rrf_score
    FROM combined
    ORDER BY rrf_score DESC
    LIMIT :top_k
    """
)


def _vector_literal(vec: list[float]) -> str:
    """Render a float vector as a pgvector literal: ``[v1,v2,...]``."""
    return f"[{','.join(str(x) for x in vec)}]"


class PgVectorHybridSearcher:
    """Runs hybrid dense+sparse search with RRF over the chunks table.

    Parameters
    ----------
    engine:
        SQLAlchemy engine pointing at the chatbot_rag database.
    corpus_sha:
        Scopes search to a single corpus snapshot.
    rrf_k:
        RRF constant (default 60, spec 02).
    w_dense, w_sparse:
        Fusion weights (default equal, spec 02).
    """

    def __init__(
        self,
        engine: Engine,
        corpus_sha: str,
        rrf_k: int = 60,
        w_dense: float = 1.0,
        w_sparse: float = 1.0,
    ) -> None:
        self._engine = engine
        self._corpus_sha = corpus_sha
        self._rrf_k = rrf_k
        self._w_dense = w_dense
        self._w_sparse = w_sparse

    @traced("hybrid_search")
    def search(
        self,
        query_vector: list[float],
        query_text: str,
        candidates: int,
        top_k: int,
    ) -> list[Candidate]:
        """Return up to *top_k* candidates ordered by descending RRF score."""
        params = {
            "qvec": _vector_literal(query_vector),
            "query_text": query_text,
            "corpus_sha": self._corpus_sha,
            "candidates": candidates,
            "top_k": top_k,
            "k": self._rrf_k,
            "w_dense": self._w_dense,
            "w_sparse": self._w_sparse,
        }
        with self._engine.connect() as conn:
            rows = conn.execute(_HYBRID_SQL, params).mappings().all()

        results = [
            Candidate(
                chunk_hash=row["chunk_hash"],
                content=row["content"],
                source=(row["metadata"] or {}).get("source", ""),
                section=(row["metadata"] or {}).get("section", ""),
                dense_rank=row["dense_rank"],
                sparse_rank=row["sparse_rank"],
                rrf_score=float(row["rrf_score"]),
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]

        dense_count = sum(1 for r in results if r.dense_rank is not None)
        sparse_count = sum(1 for r in results if r.sparse_rank is not None)
        set_span_attributes(
            dense_results_count=dense_count,
            sparse_results_count=sparse_count,
            combined_top_k=len(results),
        )
        logger.info(
            "hybrid_search: dense=%d sparse=%d combined=%d",
            dense_count,
            sparse_count,
            len(results),
        )
        return results


# Make the class satisfy the Protocol at type-check time.
_: HybridSearchPort = PgVectorHybridSearcher.__new__(PgVectorHybridSearcher)  # type: ignore[assignment]
