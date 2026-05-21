"""Unit tests for the Markdown-aware splitter.

No external dependencies; no mocking needed.
"""

from __future__ import annotations

import pytest

from app.indexing.splitter import split_markdown


class TestSplitMarkdown:
    def test_returns_list_of_dicts(self) -> None:
        text = "# Hello\n\nSome content here.\n"
        result = split_markdown(text, source="test.md")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_chunk_has_content_and_metadata(self) -> None:
        text = "# Section\n\nContent.\n"
        chunks = split_markdown(text, source="test.md")
        for chunk in chunks:
            assert "content" in chunk
            assert "metadata" in chunk
            assert "source" in chunk["metadata"]
            assert "section" in chunk["metadata"]

    def test_source_propagated(self) -> None:
        chunks = split_markdown("# A\n\ntext\n", source="docs/index.md")
        assert all(c["metadata"]["source"] == "docs/index.md" for c in chunks)

    def test_section_extracted_from_headers(self) -> None:
        text = "# Title\n\n## Sub\n\nContent.\n"
        chunks = split_markdown(text, source="x.md")
        sections = [c["metadata"]["section"] for c in chunks]
        # At least one chunk should carry a non-empty section.
        assert any(s for s in sections)

    def test_fallback_on_no_headers(self) -> None:
        text = "Plain text without any markdown headers.\n" * 10
        chunks = split_markdown(text, source="plain.md")
        assert len(chunks) > 0

    def test_large_document_split(self) -> None:
        # Generate content that exceeds chunk_size.
        text = "# BigDoc\n\n" + ("Word sentence. " * 500) + "\n"
        chunks = split_markdown(text, source="big.md")
        assert len(chunks) > 1

    def test_empty_text_returns_empty(self) -> None:
        chunks = split_markdown("", source="empty.md")
        assert chunks == []

    def test_no_duplicate_content(self) -> None:
        text = "# A\n\nHello.\n\n## B\n\nWorld.\n"
        chunks = split_markdown(text, source="dup.md")
        contents = [c["content"] for c in chunks]
        # No exact duplicates.
        assert len(contents) == len(set(contents))
