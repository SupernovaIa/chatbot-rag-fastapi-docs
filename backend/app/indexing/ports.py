"""Ports (Protocol interfaces) for the indexing feature.

Each external dependency has a thin Protocol so tests can mock them
without touching the real adapters (ADR-011).
"""

from __future__ import annotations

from typing import Protocol

from app.indexing.models import BlobItem, Chunk


class BlobLoaderPort(Protocol):
    """Lists and downloads blobs from object storage."""

    def list_blobs(self, container: str) -> list[BlobItem]:
        """Return metadata for every blob in *container*."""
        ...

    def download_blob(self, container: str, name: str) -> bytes:
        """Return the raw bytes of a blob."""
        ...


class EmbeddingsPort(Protocol):
    """Generates dense vector embeddings for text."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts and return a list of float vectors."""
        ...


class ChunkStorePort(Protocol):
    """Persists and retrieves chunks in the vector store."""

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        """Insert or update chunks. Returns the count of new rows inserted."""
        ...

    def count(self) -> int:
        """Return the total number of chunks stored."""
        ...

    def count_by_sha(self, corpus_sha: str) -> int:
        """Return the number of chunks for a specific corpus SHA."""
        ...
