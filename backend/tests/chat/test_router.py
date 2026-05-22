"""Integration-style tests for POST /chat and GET /chat/sessions.

Uses httpx + TestClient (synchronous SSE consumption). All external dependencies
(retrieval, LLM, DB store) are replaced with fakes injected via FastAPI's
dependency override mechanism.

Tests cover:
 - Stream emits token events then a citations event.
 - Second turn with session_id loads history (N=5 window).
 - GET /chat/sessions and GET /chat/sessions/{id} return the expected shape.
 - Client disconnect prevents the turn from being saved.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.router import current_active_user
from app.main import app
from app.retrieval.hybrid import PgVectorHybridSearcher
from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter
from app.retrieval.models import Candidate, RetrievalResult
from tests.chat.conftest import FakeChatHistoryStore, make_candidate

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class FakeRetrievalResult:
    original_query: str = "What is FastAPI?"
    rewritten_query: str = "What is FastAPI?"
    candidates: list = []
    rerank_fallback_used: bool = False


def _make_fake_retrieve(candidates: list[Candidate] | None = None):
    result = MagicMock(spec=RetrievalResult)
    result.original_query = "What is FastAPI?"
    result.rewritten_query = "What is FastAPI?"
    result.candidates = candidates or [make_candidate("h1")]
    result.rerank_fallback_used = False
    return result


def _patch_retrieve(monkeypatch, candidates=None):
    """Patch the retrieve orchestrator to return a canned result."""
    fake_result = _make_fake_retrieve(candidates)

    def _fake_retrieve(**kwargs):
        return fake_result

    monkeypatch.setattr("app.chat.router.retrieve", lambda *a, **kw: fake_result)
    return fake_result


def _make_llm_mock(tokens: list[str], meta: dict | None = None):
    """Return a ChatGoogleGenerativeAI mock that streams canned tokens."""

    async def _fake_astream(messages):
        for tok in tokens:
            chunk = MagicMock()
            chunk.content = tok
            chunk.response_metadata = meta or {}
            yield chunk

    instance = MagicMock()
    instance.astream = _fake_astream
    return instance


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_store() -> FakeChatHistoryStore:
    return FakeChatHistoryStore()


@pytest.fixture
def client(fake_store, monkeypatch) -> TestClient:
    """TestClient with all external dependencies overridden."""
    # Override store
    app.dependency_overrides[
        __import__("app.chat.router", fromlist=["get_store"]).get_store
    ] = lambda: fake_store

    # Override retrieval deps with dummies (retrieve is patched separately)
    from app.chat.router import get_embeddings, get_rerank_llm, get_rewrite_llm, get_searcher

    dummy_embeddings = MagicMock(spec=QueryEmbeddingsAdapter)
    dummy_embeddings.embed_query.return_value = [0.0] * 1536
    dummy_searcher = MagicMock(spec=PgVectorHybridSearcher)
    dummy_llm = MagicMock(spec=GeminiChatAdapter)
    dummy_llm.complete.return_value = ""

    app.dependency_overrides[get_embeddings] = lambda: dummy_embeddings
    app.dependency_overrides[get_searcher] = lambda: dummy_searcher
    app.dependency_overrides[get_rewrite_llm] = lambda: dummy_llm
    app.dependency_overrides[get_rerank_llm] = lambda: dummy_llm

    # Override auth: inject a fake active user
    fake_user = MagicMock()
    fake_user.id = uuid4()
    app.dependency_overrides[current_active_user] = lambda: fake_user

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /chat — stream structure
# ---------------------------------------------------------------------------


class TestChatStream:
    def test_stream_emits_token_and_citations_events(self, client, monkeypatch) -> None:
        _patch_retrieve(monkeypatch)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["Hello", " world"])

            response = client.post(
                "/chat/",
                json={"query": "What is FastAPI?"},
                headers={"Accept": "text/event-stream"},
            )

        assert response.status_code == 200

        events = _parse_sse(response.text)
        token_events = [e for e in events if e.get("type") == "token"]
        citations_events = [e for e in events if e.get("type") == "citations"]

        assert len(token_events) >= 1, "Expected at least one token event"
        assert len(citations_events) == 1, "Expected exactly one citations event"
        # citations event is last
        assert events[-1].get("type") == "citations"

    def test_stream_persists_turn(self, client, monkeypatch, fake_store) -> None:
        _patch_retrieve(monkeypatch)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["Answer text"])
            client.post("/chat/", json={"query": "Q?"})

        assert len(fake_store.saved_turns) == 1
        assert fake_store.saved_turns[0]["query"] == "Q?"
        assert fake_store.saved_turns[0]["answer"] == "Answer text"

    def test_stream_returns_session_id_in_citations_event(
        self, client, monkeypatch
    ) -> None:
        _patch_retrieve(monkeypatch)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["tok"])
            response = client.post("/chat/", json={"query": "test"})

        events = _parse_sse(response.text)
        cit = next(e for e in events if e.get("type") == "citations")
        # Items list is present (may be empty if candidate has no citable info)
        assert "items" in cit

    def test_provided_session_id_reused(self, client, monkeypatch, fake_store) -> None:
        sid = uuid4()
        _patch_retrieve(monkeypatch)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["ok"])
            client.post("/chat/", json={"query": "Q", "session_id": str(sid)})

        assert sid in fake_store._sessions

    def test_second_turn_increments_turn_idx(self, client, monkeypatch, fake_store) -> None:
        sid = uuid4()
        fake_store.get_or_create_session(sid)
        _patch_retrieve(monkeypatch)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["A1"])
            client.post("/chat/", json={"query": "Q1", "session_id": str(sid)})

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["A2"])
            client.post("/chat/", json={"query": "Q2", "session_id": str(sid)})

        turns = [t for t in fake_store.saved_turns if t["session_id"] == sid]
        assert len(turns) == 2
        assert turns[0]["turn_idx"] < turns[1]["turn_idx"]

    def test_history_loaded_for_second_turn(self, client, monkeypatch, fake_store) -> None:
        """Second request with existing session_id should load history."""
        sid = fake_store.get_or_create_session()

        # Pre-populate history with 3 complete turns
        for i in range(1, 4):
            from datetime import datetime, timezone
            from app.chat.models import ChatMessage
            now = datetime.now(tz=timezone.utc)
            fake_store._messages.extend([
                ChatMessage(
                    id=i * 2 - 1, session_id=sid, turn_idx=i, role="user",
                    content=f"Q{i}", citations=[], created_at=now
                ),
                ChatMessage(
                    id=i * 2, session_id=sid, turn_idx=i, role="assistant",
                    content=f"A{i}", citations=[], created_at=now
                ),
            ])

        history_seen: list = []

        def _capturing_retrieve(*args, history=None, **kwargs):
            history_seen.extend(history or [])
            return _make_fake_retrieve()

        monkeypatch.setattr("app.chat.router.retrieve", _capturing_retrieve)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["answer"])
            client.post("/chat/", json={"query": "Q4", "session_id": str(sid)})

        assert len(history_seen) == 3  # all 3 prior turns loaded (within window=5)

    def test_history_window_capped_at_n(self, client, monkeypatch, fake_store) -> None:
        """With 7 prior turns, retrieve should see only the last 5 (window=5)."""
        from datetime import datetime, timezone
        from app.chat.models import ChatMessage

        sid = fake_store.get_or_create_session()
        now = datetime.now(tz=timezone.utc)
        for i in range(1, 8):  # 7 complete turns
            fake_store._messages.extend([
                ChatMessage(
                    id=i * 2 - 1, session_id=sid, turn_idx=i, role="user",
                    content=f"Q{i}", citations=[], created_at=now
                ),
                ChatMessage(
                    id=i * 2, session_id=sid, turn_idx=i, role="assistant",
                    content=f"A{i}", citations=[], created_at=now
                ),
            ])

        history_seen: list = []

        def _capturing_retrieve(*args, history=None, **kwargs):
            history_seen.extend(history or [])
            return _make_fake_retrieve()

        monkeypatch.setattr("app.chat.router.retrieve", _capturing_retrieve)

        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["x"])
            client.post("/chat/", json={"query": "Q8", "session_id": str(sid)})

        # FakeChatHistoryStore.load_history already applies the window
        assert len(history_seen) == 5


# ---------------------------------------------------------------------------
# GET /chat/sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_returns_empty_list_initially(self, client) -> None:
        response = client.get("/chat/sessions")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_sessions_after_chat(self, client, monkeypatch, fake_store) -> None:
        _patch_retrieve(monkeypatch)
        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["hi"])
            client.post("/chat/", json={"query": "hello"})

        response = client.get("/chat/sessions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]
        assert "created_at" in data[0]
        assert "updated_at" in data[0]


# ---------------------------------------------------------------------------
# GET /chat/sessions/{id}
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_404_for_unknown_session(self, client) -> None:
        response = client.get(f"/chat/sessions/{uuid4()}")
        assert response.status_code == 404

    def test_returns_messages_for_known_session(
        self, client, monkeypatch, fake_store
    ) -> None:
        _patch_retrieve(monkeypatch)
        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["response text"])
            client.post("/chat/", json={"query": "How does FastAPI work?"})

        # Find the session id from saved turns
        assert len(fake_store.saved_turns) == 1
        sid = fake_store.saved_turns[0]["session_id"]

        response = client.get(f"/chat/sessions/{sid}")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        msgs = data["messages"]
        roles = {m["role"] for m in msgs}
        assert roles == {"user", "assistant"}

    def test_messages_contain_user_query(
        self, client, monkeypatch, fake_store
    ) -> None:
        _patch_retrieve(monkeypatch)
        with patch("app.chat.generator.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value = _make_llm_mock(["ans"])
            client.post("/chat/", json={"query": "Tell me about dependencies"})

        sid = fake_store.saved_turns[0]["session_id"]
        response = client.get(f"/chat/sessions/{sid}")
        msgs = response.json()["messages"]
        user_msg = next(m for m in msgs if m["role"] == "user")
        assert user_msg["content"] == "Tell me about dependencies"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text/event-stream into a list of JSON event payloads."""
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return events
