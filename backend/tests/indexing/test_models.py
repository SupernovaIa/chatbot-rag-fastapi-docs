"""Unit tests for the Chunk domain model."""

from __future__ import annotations

import hashlib

from app.indexing.models import Chunk


class TestChunk:
    def _make_chunk(self, content: str = "hello", corpus_sha: str = "abc") -> Chunk:
        return Chunk(
            content=content,
            embedding=[0.1] * 1536,
            metadata={"source": "test.md", "section": "Intro"},
            corpus_sha=corpus_sha,
        )

    def test_chunk_hash_is_deterministic(self) -> None:
        c1 = self._make_chunk("same content", "sha1")
        c2 = self._make_chunk("same content", "sha1")
        assert c1.chunk_hash == c2.chunk_hash

    def test_chunk_hash_differs_on_content_change(self) -> None:
        c1 = self._make_chunk("content A", "sha1")
        c2 = self._make_chunk("content B", "sha1")
        assert c1.chunk_hash != c2.chunk_hash

    def test_chunk_hash_differs_on_corpus_sha_change(self) -> None:
        c1 = self._make_chunk("same", "sha1")
        c2 = self._make_chunk("same", "sha2")
        assert c1.chunk_hash != c2.chunk_hash

    def test_chunk_hash_matches_manual_sha256(self) -> None:
        content = "test content"
        corpus_sha = "deadbeef"
        chunk = self._make_chunk(content, corpus_sha)
        expected = hashlib.sha256(f"{content}{corpus_sha}".encode()).hexdigest()
        assert chunk.chunk_hash == expected

    def test_indexed_at_is_set(self) -> None:
        chunk = self._make_chunk()
        assert chunk.indexed_at is not None
