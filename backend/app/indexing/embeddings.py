"""Gemini embeddings adapter with batching, backoff, and L2 normalisation.

Model: gemini-embedding-001
Dimensionality: 1536 (MRL truncation via output_dimensionality param).

Spec 01 note: Only the full 3072-dim output is guaranteed to be L2-normalised
by the model.  After MRL truncation to 1536, we renormalise the vector.

Rate-limit strategy:
- Default batch size: 50 texts (conservative for free tier).
- tenacity exponential backoff: 1 s → 2 s → 4 s → ... (max 60 s, 8 retries).
- On ResourceExhausted (429) the whole batch is retried after waiting.

SDK: google-genai >= 1.0 (replaces deprecated google-generativeai).
"""

from __future__ import annotations

import logging
import math
from typing import Generator

from google import genai
from google.genai import types as genai_types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.indexing.ports import EmbeddingsPort

logger = logging.getLogger(__name__)

# Model ID anchored 2026-05-20 per CLAUDE.md policy.
_MODEL_ID = "gemini-embedding-001"
_OUTPUT_DIM = 1536
_DEFAULT_BATCH_SIZE = 50
_MAX_RETRIES = 8
_WAIT_MIN = 1
_WAIT_MAX = 60


def _l2_normalize(vec: list[float]) -> list[float]:
    """Return a L2-normalised copy of *vec*."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def _batched(items: list, batch_size: int) -> Generator[list, None, None]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


class GeminiEmbeddingsAdapter:
    """Adapter that calls the Gemini embedding API.

    Parameters
    ----------
    api_key:
        Google AI Studio API key.
    batch_size:
        Number of texts per API call (default 50).
    task_type:
        Gemini embedding task type.  Use ``"RETRIEVAL_DOCUMENT"`` for
        corpus chunks and ``"RETRIEVAL_QUERY"`` at query time.
    """

    def __init__(
        self,
        api_key: str,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._batch_size = batch_size
        self._task_type = task_type

    # --- EmbeddingsPort ---

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed all *texts* in batches.  Returns one vector per text."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        total_batches = math.ceil(len(texts) / self._batch_size)

        for batch_idx, batch in enumerate(_batched(texts, self._batch_size), start=1):
            logger.info(
                "Embedding batch %d/%d (%d texts)",
                batch_idx,
                total_batches,
                len(batch),
            )
            batch_embeddings = self._embed_with_backoff(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=_WAIT_MIN, max=_WAIT_MAX),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _embed_with_backoff(self, texts: list[str]) -> list[list[float]]:
        """Call the API for one batch with automatic retry on any error."""
        response = self._client.models.embed_content(
            model=_MODEL_ID,
            contents=texts,
            config=genai_types.EmbedContentConfig(
                task_type=self._task_type,
                output_dimensionality=_OUTPUT_DIM,
            ),
        )
        # response.embeddings is a list of ContentEmbedding objects.
        return [_l2_normalize(list(emb.values)) for emb in response.embeddings]


# Make the class satisfy the Protocol at type-check time.
_: EmbeddingsPort = GeminiEmbeddingsAdapter.__new__(GeminiEmbeddingsAdapter)  # type: ignore[assignment]
