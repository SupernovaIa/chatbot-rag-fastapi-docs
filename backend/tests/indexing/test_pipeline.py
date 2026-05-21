"""Integration-style unit tests for the indexing pipeline.

All external dependencies (loader, embeddings, store) are replaced with
in-memory fakes so no network or DB connection is required.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from app.indexing.models import BlobItem, Chunk
from app.indexing.pipeline import run_indexing


# ---------------------------------------------------------------------------
# Fakes (implement the Port protocols in memory)
# ---------------------------------------------------------------------------

class FakeBlobLoader:
    def __init__(self, blobs: dict[str, bytes]) -> None:
        """blobs: mapping from blob name → raw bytes."""
        self._blobs = blobs

    def list_blobs(self, container: str) -> list[BlobItem]:
        return [BlobItem(name=name, size=len(data)) for name, data in self._blobs.items()]

    def download_blob(self, container: str, name: str) -> bytes:
        return self._blobs[name]


class FakeEmbeddings:
    """Returns deterministic zero-ish vectors (unit vector on dim 0)."""

    def __init__(self, dim: int = 1536) -> None:
        self._dim = dim
        self.call_count = 0
        self.last_texts: list[str] = []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        self.last_texts = list(texts)
        vec = [0.0] * self._dim
        vec[0] = 1.0
        return [list(vec) for _ in texts]


class FakeChunkStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._hashes: set[str] = set()

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        inserted = 0
        for chunk in chunks:
            if chunk.chunk_hash not in self._hashes:
                self._chunks.append(chunk)
                self._hashes.add(chunk.chunk_hash)
                inserted += 1
        return inserted

    def count(self) -> int:
        return len(self._chunks)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CORPUS_SHA = "abc123"

_SAMPLE_MD = b"""# FastAPI Introduction

FastAPI is a modern web framework for building APIs with Python.

## Features

- Fast
- Easy to use
- Based on standard Python type hints
"""


@pytest.fixture
def loader() -> FakeBlobLoader:
    return FakeBlobLoader({"tutorial/index.md": _SAMPLE_MD})


@pytest.fixture
def embeddings() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture
def store() -> FakeChunkStore:
    return FakeChunkStore()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunIndexing:
    def test_basic_run_returns_stats(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        result = run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        assert result["blobs_processed"] >= 1
        assert result["chunks_split"] > 0
        assert result["chunks_inserted"] > 0
        assert result["total_in_store"] > 0

    def test_chunks_have_correct_metadata(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        for chunk in store._chunks:
            assert chunk.metadata["source"] == "tutorial/index.md"
            assert chunk.metadata["corpus_sha"] == _CORPUS_SHA
            assert "section" in chunk.metadata

    def test_chunks_have_non_null_embeddings(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        for chunk in store._chunks:
            assert len(chunk.embedding) == 1536
            assert chunk.embedding[0] == 1.0  # matches FakeEmbeddings

    def test_idempotency_no_duplicate_chunks(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        result1 = run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        count_after_first = store.count()

        result2 = run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)

        assert store.count() == count_after_first  # no new rows
        assert result2["chunks_inserted"] == 0

    def test_dry_run_does_not_insert(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        result = run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA, dry_run=True)
        assert result["chunks_inserted"] == 0
        assert store.count() == 0

    def test_non_md_blobs_skipped(
        self, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        loader = FakeBlobLoader({
            "docs.md": _SAMPLE_MD,
            "image.png": b"\x89PNG",
            "config.yaml": b"key: value",
        })
        result = run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        # Only docs.md should have been processed.
        assert result["blobs_processed"] == 3
        assert result["chunks_split"] > 0
        # PNG and YAML blobs produce no chunks.
        sources = {c.metadata["source"] for c in store._chunks}
        assert "image.png" not in sources
        assert "config.yaml" not in sources

    def test_multiple_blobs_all_indexed(
        self, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        loader = FakeBlobLoader({
            "a.md": b"# A\n\nContent A.\n",
            "b.md": b"# B\n\nContent B.\n",
        })
        run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        sources = {c.metadata["source"] for c in store._chunks}
        assert "a.md" in sources
        assert "b.md" in sources

    def test_embeddings_called_with_all_texts(
        self, loader: FakeBlobLoader, embeddings: FakeEmbeddings, store: FakeChunkStore
    ) -> None:
        run_indexing(loader, embeddings, store, corpus_sha=_CORPUS_SHA)
        assert embeddings.call_count >= 1
        assert len(embeddings.last_texts) > 0
