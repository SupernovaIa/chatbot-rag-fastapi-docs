"""High-level indexing pipeline.

Orchestrates: blob listing → download → split → embed → store.
Called by scripts/index_corpus.py; not exposed as a FastAPI route.
"""

from __future__ import annotations

import logging

from app.indexing.models import Chunk
from app.indexing.ports import BlobLoaderPort, ChunkStorePort, EmbeddingsPort
from app.indexing.splitter import split_markdown

logger = logging.getLogger(__name__)

_CONTAINER = "corpus"


def run_indexing(
    loader: BlobLoaderPort,
    embeddings: EmbeddingsPort,
    store: ChunkStorePort,
    corpus_sha: str,
    container: str = _CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Run the full indexing pipeline.

    Parameters
    ----------
    loader:
        Blob loader adapter (AzuriteBlobLoader or mock).
    embeddings:
        Embeddings adapter (GeminiEmbeddingsAdapter or mock).
    store:
        Chunk store adapter (PgVectorChunkStore or mock).
    corpus_sha:
        Git commit SHA that identifies the corpus snapshot.
    container:
        Blob container name.
    dry_run:
        If True, skip the store step and just return stats.

    Returns
    -------
    dict with keys: blobs_processed, chunks_split, chunks_inserted, total_in_store.
    """
    blobs = loader.list_blobs(container)
    logger.info("Found %d blobs in container '%s'", len(blobs), container)

    all_chunk_dicts: list[dict] = []
    for blob in blobs:
        if not blob.name.endswith(".md"):
            continue
        raw = loader.download_blob(container, blob.name)
        text = raw.decode("utf-8", errors="replace")
        chunks = split_markdown(text, source=blob.name)
        for c in chunks:
            c["metadata"]["corpus_sha"] = corpus_sha
        all_chunk_dicts.extend(chunks)

    logger.info("Total chunks after splitting: %d", len(all_chunk_dicts))

    if not all_chunk_dicts:
        return {
            "blobs_processed": len(blobs),
            "chunks_split": 0,
            "chunks_inserted": 0,
            "total_in_store": store.count(),
        }

    texts = [c["content"] for c in all_chunk_dicts]
    vectors = embeddings.embed_batch(texts)

    chunks: list[Chunk] = []
    for chunk_dict, vector in zip(all_chunk_dicts, vectors):
        chunks.append(
            Chunk(
                content=chunk_dict["content"],
                embedding=vector,
                metadata=chunk_dict["metadata"],
                corpus_sha=corpus_sha,
            )
        )

    inserted = 0
    if not dry_run:
        inserted = store.upsert_chunks(chunks)
    else:
        logger.info("dry_run=True, skipping store step")

    total = store.count()
    result = {
        "blobs_processed": len(blobs),
        "chunks_split": len(chunks),
        "chunks_inserted": inserted,
        "total_in_store": total,
    }
    logger.info("Indexing complete: %s", result)
    return result
