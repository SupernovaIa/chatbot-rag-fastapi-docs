"""Unit tests for GeminiEmbeddingsAdapter with the API mocked.

Uses unittest.mock to intercept the google.genai client so no real API call
is made.  Tests verify batching, L2 normalisation, and backoff retry logic.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from google.genai import errors as genai_errors

from app.indexing.embeddings import (
    GeminiEmbeddingsAdapter,
    _is_retryable,
    _l2_normalize,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_fake_vector(dim: int = 1536, value: float = 1.0) -> list[float]:
    """Return a non-normalised vector to test normalisation."""
    return [value] * dim


def _make_embed_response(texts: list[str], dim: int = 1536):
    """Fake response from client.models.embed_content (google-genai SDK)."""
    embeddings = [SimpleNamespace(values=_make_fake_vector(dim)) for _ in texts]
    return SimpleNamespace(embeddings=embeddings)


# ---------------------------------------------------------------------------
# _is_retryable
# ---------------------------------------------------------------------------

class TestIsRetryable:
    def _api_error(self, code: int) -> genai_errors.APIError:
        return genai_errors.APIError(code, {"error": {"message": f"HTTP {code}"}})

    def test_429_is_retryable(self) -> None:
        assert _is_retryable(self._api_error(429)) is True

    def test_500_is_retryable(self) -> None:
        assert _is_retryable(self._api_error(500)) is True

    def test_503_is_retryable(self) -> None:
        assert _is_retryable(self._api_error(503)) is True

    def test_408_is_retryable(self) -> None:
        assert _is_retryable(self._api_error(408)) is True

    def test_400_not_retryable(self) -> None:
        assert _is_retryable(self._api_error(400)) is False

    def test_404_not_retryable(self) -> None:
        assert _is_retryable(self._api_error(404)) is False

    def test_connection_error_is_retryable(self) -> None:
        assert _is_retryable(ConnectionError("reset")) is True

    def test_timeout_error_is_retryable(self) -> None:
        assert _is_retryable(TimeoutError("timed out")) is True

    def test_type_error_not_retryable(self) -> None:
        assert _is_retryable(TypeError("bad type")) is False

    def test_value_error_not_retryable(self) -> None:
        assert _is_retryable(ValueError("bad value")) is False

    def test_runtime_error_not_retryable(self) -> None:
        assert _is_retryable(RuntimeError("unexpected")) is False


# ---------------------------------------------------------------------------
# _l2_normalize
# ---------------------------------------------------------------------------

class TestL2Normalize:
    def test_unit_vector_unchanged(self) -> None:
        vec = [1.0, 0.0, 0.0]
        result = _l2_normalize(vec)
        assert abs(result[0] - 1.0) < 1e-9
        assert abs(result[1]) < 1e-9

    def test_all_ones_normalised(self) -> None:
        vec = [1.0, 1.0]
        result = _l2_normalize(vec)
        norm = math.sqrt(sum(x * x for x in result))
        assert abs(norm - 1.0) < 1e-6

    def test_zero_vector_returned_as_is(self) -> None:
        vec = [0.0, 0.0, 0.0]
        result = _l2_normalize(vec)
        assert result == vec

    def test_output_length_preserved(self) -> None:
        vec = [2.0, 3.0, 4.0]
        result = _l2_normalize(vec)
        assert len(result) == len(vec)


# ---------------------------------------------------------------------------
# GeminiEmbeddingsAdapter.embed_batch
# ---------------------------------------------------------------------------

class TestGeminiEmbeddingsAdapterEmbedBatch:
    """Patch _client.models.embed_content on the adapter instance."""

    def _make_adapter(self, batch_size: int = 10) -> GeminiEmbeddingsAdapter:
        adapter = GeminiEmbeddingsAdapter.__new__(GeminiEmbeddingsAdapter)
        adapter._batch_size = batch_size
        adapter._task_type = "RETRIEVAL_DOCUMENT"
        adapter._client = MagicMock()
        return adapter

    def _setup_mock(self, adapter: GeminiEmbeddingsAdapter, side_effect=None) -> MagicMock:
        mock = adapter._client.models.embed_content
        if side_effect:
            mock.side_effect = side_effect
        else:
            mock.side_effect = lambda **kw: _make_embed_response(kw["contents"])
        return mock

    def test_returns_one_vector_per_text(self) -> None:
        adapter = self._make_adapter()
        self._setup_mock(adapter)
        texts = ["hello", "world", "foo"]
        result = adapter.embed_batch(texts)
        assert len(result) == len(texts)

    def test_each_vector_is_l2_normalised(self) -> None:
        adapter = self._make_adapter()
        self._setup_mock(adapter)
        result = adapter.embed_batch(["a", "b"])
        for vec in result:
            norm = math.sqrt(sum(x * x for x in vec))
            assert abs(norm - 1.0) < 1e-6

    def test_batching_calls_api_multiple_times(self) -> None:
        adapter = self._make_adapter(batch_size=2)
        call_count = 0

        def fake_embed(**kw):
            nonlocal call_count
            call_count += 1
            return _make_embed_response(kw["contents"])

        self._setup_mock(adapter, side_effect=fake_embed)
        texts = ["a", "b", "c", "d", "e"]  # ceil(5/2) = 3 batches
        result = adapter.embed_batch(texts)
        assert call_count == 3
        assert len(result) == 5

    def test_empty_input_returns_empty(self) -> None:
        adapter = self._make_adapter()
        result = adapter.embed_batch([])
        adapter._client.models.embed_content.assert_not_called()
        assert result == []

    def test_vector_dimension_matches_output_dim(self) -> None:
        adapter = self._make_adapter()
        self._setup_mock(adapter)
        result = adapter.embed_batch(["test"])
        assert len(result[0]) == 1536

    def test_output_dimensionality_passed_to_api(self) -> None:
        """Verify that output_dimensionality=1536 is in the EmbedContentConfig."""
        adapter = self._make_adapter()
        captured: dict = {}

        def fake_embed(**kw):
            captured.update(kw)
            return _make_embed_response(kw["contents"])

        self._setup_mock(adapter, side_effect=fake_embed)
        adapter.embed_batch(["test"])

        config = captured.get("config")
        assert config is not None
        assert config.output_dimensionality == 1536

    def test_retry_on_transient_connection_error(self) -> None:
        """Transient network error triggers retry and eventually succeeds."""
        adapter = self._make_adapter(batch_size=1)
        call_count = 0

        def flaky_embed(**kw):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("connection reset by peer")
            return _make_embed_response(kw["contents"])

        self._setup_mock(adapter, side_effect=flaky_embed)
        result = adapter.embed_batch(["retry-me"])
        assert call_count == 2
        assert len(result) == 1

    def test_retry_on_api_error_429(self) -> None:
        """APIError with code 429 (quota) triggers retry."""
        adapter = self._make_adapter(batch_size=1)
        call_count = 0

        def quota_embed(**kw):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise genai_errors.APIError(429, {"error": {"message": "quota exceeded"}})
            return _make_embed_response(kw["contents"])

        self._setup_mock(adapter, side_effect=quota_embed)
        result = adapter.embed_batch(["retry-429"])
        assert call_count == 2
        assert len(result) == 1

    def test_non_retryable_error_not_retried(self) -> None:
        """Programming errors (TypeError) must NOT trigger retry — surfaced immediately."""
        adapter = self._make_adapter(batch_size=1)
        call_count = 0

        def buggy_embed(**kw):
            nonlocal call_count
            call_count += 1
            raise TypeError("unexpected type in embedding call")

        self._setup_mock(adapter, side_effect=buggy_embed)
        with pytest.raises(TypeError):
            adapter.embed_batch(["test"])
        assert call_count == 1  # no retry, fails on first attempt

    def test_non_retryable_api_error_400_not_retried(self) -> None:
        """APIError 400 (bad request / invalid input) must NOT trigger retry."""
        adapter = self._make_adapter(batch_size=1)
        call_count = 0

        def bad_request_embed(**kw):
            nonlocal call_count
            call_count += 1
            raise genai_errors.APIError(400, {"error": {"message": "invalid request"}})

        self._setup_mock(adapter, side_effect=bad_request_embed)
        with pytest.raises(genai_errors.APIError) as exc_info:
            adapter.embed_batch(["test"])
        assert exc_info.value.code == 400
        assert call_count == 1  # no retry
