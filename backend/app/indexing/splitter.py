"""Markdown-aware text splitter for the corpus.

Strategy (spec 01):
1. Try MarkdownHeaderTextSplitter to preserve header context in metadata.
2. Each section is then split by RecursiveCharacterTextSplitter with
   chunk_size=512 tokens and chunk_overlap=80 tokens (tiktoken cl100k_base
   approximation for Gemini, which does not expose a public tokenizer).

The two-step approach means a chunk always carries its nearest H1/H2/H3
ancestor in the ``section`` metadata field.
"""

from __future__ import annotations

import logging

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Headers to split on — captures up to H3.
_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

# 512 token target, 80 token overlap, using tiktoken cl100k_base as proxy.
_CHUNK_SIZE = 512
_CHUNK_OVERLAP = 80


def _make_recursive_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )


def split_markdown(text: str, source: str) -> list[dict]:
    """Split *text* into chunks and return a list of dicts.

    Each dict has:
    - ``content``: the chunk text
    - ``metadata``: ``{"source": source, "section": "<h1> > <h2> > ..."}``

    Parameters
    ----------
    text:
        Raw Markdown content of a document.
    source:
        The blob name / relative path used as the ``source`` metadata field.
    """
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    recursive_splitter = _make_recursive_splitter()

    try:
        header_docs = md_splitter.split_text(text)
    except Exception:
        logger.warning("MarkdownHeaderSplitter failed for '%s', falling back to recursive", source)
        header_docs = []

    if not header_docs:
        # Pure fallback: no headers found or splitter errored.
        chunks_text = recursive_splitter.split_text(text)
        return [
            {"content": c, "metadata": {"source": source, "section": ""}}
            for c in chunks_text
            if c.strip()
        ]

    results: list[dict] = []
    for doc in header_docs:
        # Build a human-readable section label from header metadata.
        section_parts = [
            doc.metadata.get("h1", ""),
            doc.metadata.get("h2", ""),
            doc.metadata.get("h3", ""),
        ]
        section = " > ".join(p for p in section_parts if p)

        # Further split each header section if it's too large.
        sub_chunks = recursive_splitter.split_text(doc.page_content)
        for chunk in sub_chunks:
            if chunk.strip():
                results.append(
                    {"content": chunk, "metadata": {"source": source, "section": section}}
                )

    logger.debug("split_markdown('%s'): %d chunks", source, len(results))
    return results
