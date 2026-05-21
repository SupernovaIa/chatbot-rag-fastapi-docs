"""Adapters for retrieval-time external calls: query embeddings and chat LLM.

- ``QueryEmbeddingsAdapter`` reuses the indexing ``GeminiEmbeddingsAdapter`` but
  with task type ``RETRIEVAL_QUERY`` (the corpus uses ``RETRIEVAL_DOCUMENT``).
- ``GeminiChatAdapter`` wraps LangChain's ``ChatGoogleGenerativeAI`` so the
  OpenInference LangChain instrumentor traces every reranker/rewriter call
  automatically (ADR-008).
"""

from __future__ import annotations

import logging

from app.indexing.embeddings import GeminiEmbeddingsAdapter
from app.retrieval.ports import ChatLLMPort, QueryEmbeddingsPort

logger = logging.getLogger(__name__)


def _extract_text(content: object) -> str:
    """Flatten a LangChain message content into plain text.

    Gemini 3.x "thinking" models return content as a list of blocks, e.g.
    ``[{"type": "text", "text": "..."}]`` (plus reasoning blocks). Earlier
    models return a plain string. This handles both and ignores non-text
    blocks (thinking, signatures).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


class QueryEmbeddingsAdapter:
    """Embeds queries with ``gemini-embedding-001`` (RETRIEVAL_QUERY)."""

    def __init__(self, api_key: str) -> None:
        self._adapter = GeminiEmbeddingsAdapter(
            api_key=api_key,
            batch_size=1,
            task_type="RETRIEVAL_QUERY",
        )

    def embed_query(self, text: str) -> list[float]:
        vectors = self._adapter.embed_batch([text])
        return vectors[0]


class GeminiChatAdapter:
    """Chat completion via LangChain ChatGoogleGenerativeAI (Gemini Flash).

    The request *timeout* is set on the underlying client. When exceeded, the
    SDK raises, which the reranker/rewriter fallback paths catch (so a slow
    Flash call degrades to the hybrid order instead of hanging). The reranker
    and rewriter use separate adapters with their own timeouts.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float | None = None,
    ) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._model_id = model
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            timeout=timeout,
        )

    def complete(self, prompt: str) -> str:
        response = self._llm.invoke(prompt)
        return _extract_text(response.content)


# Make the classes satisfy the Protocols at type-check time.
_e: QueryEmbeddingsPort = QueryEmbeddingsAdapter.__new__(QueryEmbeddingsAdapter)  # type: ignore[assignment]
_c: ChatLLMPort = GeminiChatAdapter.__new__(GeminiChatAdapter)  # type: ignore[assignment]
