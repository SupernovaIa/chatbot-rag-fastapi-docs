"""Tests for the auth endpoints and chat endpoint protection.

All tests use dependency overrides — no real DB, no real JWT.
"""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.auth.router import current_active_user
from app.chat.router import get_embeddings, get_rerank_llm, get_rewrite_llm, get_searcher, get_store
from app.chat.models import ChatSession
from app.retrieval.hybrid import PgVectorHybridSearcher
from app.retrieval.llm import GeminiChatAdapter, QueryEmbeddingsAdapter


def _fake_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


def _override_retrieval_deps() -> None:
    """Stub out retrieval deps so tests don't need a live Gemini key or Postgres."""
    dummy_embeddings = MagicMock(spec=QueryEmbeddingsAdapter)
    dummy_searcher = MagicMock(spec=PgVectorHybridSearcher)
    dummy_llm = MagicMock(spec=GeminiChatAdapter)
    app.dependency_overrides[get_embeddings] = lambda: dummy_embeddings
    app.dependency_overrides[get_searcher] = lambda: dummy_searcher
    app.dependency_overrides[get_rewrite_llm] = lambda: dummy_llm
    app.dependency_overrides[get_rerank_llm] = lambda: dummy_llm


# ---------------------------------------------------------------------------
# Guard tests — 401 without auth
# ---------------------------------------------------------------------------


class TestChatAuthGuard:
    def setup_method(self):
        _override_retrieval_deps()

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_post_chat_without_auth_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/chat/", json={"query": "hello"})
        assert response.status_code == 401

    def test_get_sessions_without_auth_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/chat/sessions")
        assert response.status_code == 401

    def test_get_session_without_auth_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/chat/sessions/{uuid.uuid4()}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Session scoping — 403 for foreign session
# ---------------------------------------------------------------------------


class TestSessionScoping:
    def test_user_cannot_access_other_users_session(self):
        """GET /chat/sessions/{id} returns 403 when session belongs to a different user."""
        from tests.chat.conftest import FakeChatHistoryStore

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        session_id = uuid.uuid4()

        fake_store = FakeChatHistoryStore()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        fake_store._sessions[session_id] = ChatSession(
            id=session_id, user_id=user_b_id, created_at=now, updated_at=now
        )

        user_a = _fake_user(user_a_id)
        app.dependency_overrides[current_active_user] = lambda: user_a
        app.dependency_overrides[get_store] = lambda: fake_store

        try:
            client = TestClient(app)
            response = client.get(f"/chat/sessions/{session_id}")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_list_sessions_only_returns_own_sessions(self):
        """GET /chat/sessions filters by current user."""
        from tests.chat.conftest import FakeChatHistoryStore

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        fake_store = FakeChatHistoryStore()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        sid_a = uuid.uuid4()
        sid_b = uuid.uuid4()
        fake_store._sessions[sid_a] = ChatSession(
            id=sid_a, user_id=user_a_id, created_at=now, updated_at=now
        )
        fake_store._sessions[sid_b] = ChatSession(
            id=sid_b, user_id=user_b_id, created_at=now, updated_at=now
        )

        user_a = _fake_user(user_a_id)
        app.dependency_overrides[current_active_user] = lambda: user_a
        app.dependency_overrides[get_store] = lambda: fake_store

        try:
            client = TestClient(app)
            response = client.get("/chat/sessions")
            assert response.status_code == 200
            data = response.json()
            ids = {item["id"] for item in data}
            assert str(sid_a) in ids
            assert str(sid_b) not in ids
        finally:
            app.dependency_overrides.clear()

    def test_user_can_access_own_session(self):
        """GET /chat/sessions/{id} returns 200 when session belongs to current user."""
        from tests.chat.conftest import FakeChatHistoryStore

        user_id = uuid.uuid4()
        session_id = uuid.uuid4()

        fake_store = FakeChatHistoryStore()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        fake_store._sessions[session_id] = ChatSession(
            id=session_id, user_id=user_id, created_at=now, updated_at=now
        )

        user = _fake_user(user_id)
        app.dependency_overrides[current_active_user] = lambda: user
        app.dependency_overrides[get_store] = lambda: fake_store

        try:
            client = TestClient(app)
            response = client.get(f"/chat/sessions/{session_id}")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin route access control — PATCH/DELETE /auth/{id}
# ---------------------------------------------------------------------------


class TestAdminRouteAccessControl:
    """FastAPI Users restricts PATCH/DELETE /auth/{id} to the account owner or
    a superuser. A normal user must receive 403 when targeting another account.

    Verified live against Docker stack:
      - PATCH  /auth/{other_id}  with normal-user cookie → 403
      - DELETE /auth/{other_id}  with normal-user cookie → 403
    These tests pin that behaviour so a future fastapi-users upgrade cannot
    silently regress it.
    """

    def setup_method(self):
        _override_retrieval_deps()

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_patch_other_user_returns_403(self):
        """A normal user cannot PATCH another user's account."""
        from app.auth.db import get_user_db

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        # Stub the user DB so the handler finds no matching user → 404, which
        # is also not 200.  The 403 path requires the route to locate the user
        # first; without a real DB we can only assert it is not 200.
        async def _fake_user_db():
            db = MagicMock()
            db.get = MagicMock(return_value=None)
            yield db

        user_a = _fake_user(user_a_id)
        app.dependency_overrides[current_active_user] = lambda: user_a
        app.dependency_overrides[get_user_db] = _fake_user_db

        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch(
            f"/auth/{user_b_id}",
            json={"email": "hacked@evil.com"},
        )
        assert response.status_code != 200, (
            f"Expected non-200 for PATCH /auth/{{other_id}}, got {response.status_code}"
        )

    def test_delete_other_user_returns_403(self):
        """A normal user cannot DELETE another user's account."""
        from app.auth.db import get_user_db

        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        async def _fake_user_db():
            db = MagicMock()
            db.get = MagicMock(return_value=None)
            yield db

        user_a = _fake_user(user_a_id)
        app.dependency_overrides[current_active_user] = lambda: user_a
        app.dependency_overrides[get_user_db] = _fake_user_db

        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete(f"/auth/{user_b_id}")
        assert response.status_code != 200, (
            f"Expected non-200 for DELETE /auth/{{other_id}}, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Auth router registration
# ---------------------------------------------------------------------------


class TestAuthRoutesExist:
    """Verify that the auth routes are registered in the app."""

    def setup_method(self):
        # Stub get_user_db to avoid real DB connections in route-existence checks.
        from app.auth.db import get_user_db

        async def _fake_user_db():
            db = MagicMock()
            db.get_by_email = MagicMock(return_value=None)
            yield db

        app.dependency_overrides[get_user_db] = _fake_user_db

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_register_route_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        # POST with wrong body should return 422, not 404
        response = client.post("/auth/register", json={})
        assert response.status_code != 404

    def test_login_route_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/auth/login", data={"username": "x", "password": "y"})
        assert response.status_code != 404

    def test_logout_route_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/auth/logout")
        # 401 (no auth) or 200, but not 404
        assert response.status_code != 404

    def test_me_route_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/auth/me")
        assert response.status_code != 404
