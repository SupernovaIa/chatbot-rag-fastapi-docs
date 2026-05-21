"""Domain models for the indexing feature (pure dataclasses, no ORM)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BlobItem:
    """Minimal metadata returned by BlobLoaderPort.list_blobs."""

    name: str
    size: int
    etag: str = ""


@dataclass
class Chunk:
    """A document chunk ready to be stored in pgvector.

    The *chunk_hash* is the SHA-256 of (content + corpus_sha).
    It acts as the idempotency key for upserts.
    """

    content: str
    embedding: list[float]
    metadata: dict  # {"source": str, "section": str, "corpus_sha": str}
    corpus_sha: str
    chunk_hash: str = field(init=False)
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.chunk_hash = hashlib.sha256(
            f"{self.content}{self.corpus_sha}".encode()
        ).hexdigest()
