"""Shared fakes for retrieval unit tests (no network, no DB)."""

from __future__ import annotations

from contextlib import contextmanager

from app.retrieval.models import Candidate


class FakeLLM:
    """Chat LLM port double. Returns a canned response or raises."""

    def __init__(self, response: str = "", raises: Exception | None = None) -> None:
        self.response = response
        self.raises = raises
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.raises is not None:
            raise self.raises
        return self.response


class FakeEmbeddings:
    """Query embeddings port double. Returns a fixed unit vector."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim
        self.last_text: str | None = None

    def embed_query(self, text: str) -> list[float]:
        self.last_text = text
        vec = [0.0] * self.dim
        vec[0] = 1.0
        return vec


class FakeSearcher:
    """Hybrid search port double. Returns a preset candidate list."""

    def __init__(self, candidates: list[Candidate]) -> None:
        self._candidates = candidates
        self.last_query_text: str | None = None

    def search(self, query_vector, query_text, candidates, top_k):
        self.last_query_text = query_text
        return list(self._candidates[:top_k])


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeResult":
        return self

    def all(self) -> list[dict]:
        return self._rows


class FakeEngine:
    """SQLAlchemy engine double whose connection yields preset rows."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_params: dict | None = None

    @contextmanager
    def connect(self):
        engine = self

        class _Conn:
            def execute(self, stmt, params=None):
                engine.last_params = params
                return _FakeResult(engine._rows)

        yield _Conn()


def make_candidate(cid: str, content: str = "", rrf: float = 0.0, **kw) -> Candidate:
    return Candidate(
        chunk_hash=cid,
        content=content or f"content of {cid}",
        source=kw.get("source", f"{cid}.md"),
        section=kw.get("section", "Section"),
        dense_rank=kw.get("dense_rank"),
        sparse_rank=kw.get("sparse_rank"),
        rrf_score=rrf,
    )
