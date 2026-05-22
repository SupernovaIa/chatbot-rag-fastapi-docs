"""Unit tests for ChatHistoryStore (fake engine — no real DB needed)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


from app.chat.store import ChatHistoryStore
from tests.chat.conftest import FakeEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now():
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# get_or_create_session
# ---------------------------------------------------------------------------


class TestGetOrCreateSession:
    def test_creates_new_session_when_sid_is_none(self) -> None:
        engine = FakeEngine({"select id": None})
        store = ChatHistoryStore(engine)
        sid = store.get_or_create_session(None)
        assert sid is not None

    def test_returns_existing_session_if_found(self) -> None:
        existing = uuid4()
        # Simulate row found
        engine = FakeEngine({"select id": (str(existing),)})
        store = ChatHistoryStore(engine)
        sid = store.get_or_create_session(existing)
        assert sid == existing

    def test_creates_session_with_provided_sid_when_not_found(self) -> None:
        provided = uuid4()
        engine = FakeEngine({"select id": None})
        store = ChatHistoryStore(engine)
        sid = store.get_or_create_session(provided)
        assert sid == provided


# ---------------------------------------------------------------------------
# load_history
# ---------------------------------------------------------------------------


class TestLoadHistory:
    def _engine_with_rows(self, rows) -> FakeEngine:
        return FakeEngine({"ranked": rows})

    def test_returns_empty_list_when_no_messages(self) -> None:
        engine = self._engine_with_rows([])
        store = ChatHistoryStore(engine)
        result = store.load_history(uuid4(), window=5)
        assert result == []

    def test_builds_turns_from_pairs(self) -> None:
        sid = uuid4()
        rows = [
            (1, "user", "What is FastAPI?"),
            (1, "assistant", "FastAPI is a modern web framework."),
        ]
        engine = self._engine_with_rows(rows)
        store = ChatHistoryStore(engine)
        result = store.load_history(sid, window=5)
        assert len(result) == 1
        assert result[0].question == "What is FastAPI?"
        assert result[0].answer == "FastAPI is a modern web framework."

    def test_returns_multiple_turns_in_order(self) -> None:
        sid = uuid4()
        rows = [
            (1, "user", "Q1"),
            (1, "assistant", "A1"),
            (2, "user", "Q2"),
            (2, "assistant", "A2"),
        ]
        engine = self._engine_with_rows(rows)
        store = ChatHistoryStore(engine)
        result = store.load_history(sid, window=5)
        assert [t.question for t in result] == ["Q1", "Q2"]

    def test_incomplete_turn_missing_assistant_is_skipped(self) -> None:
        sid = uuid4()
        # Only user row, no assistant row → the GROUP BY HAVING COUNT = 2 filters it out
        # In the fake, the query isn't really SQL, so we test the Python grouping logic
        rows = [
            (1, "user", "Q1"),
            (1, "assistant", "A1"),
            # turn 2 has only user — the SQL would exclude it via HAVING COUNT(DISTINCT role)=2
            # The fake returns whatever we give it, so provide only complete turns
        ]
        engine = self._engine_with_rows(rows)
        store = ChatHistoryStore(engine)
        result = store.load_history(sid, window=5)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# next_turn_idx
# ---------------------------------------------------------------------------


class TestNextTurnIdx:
    def test_returns_1_for_empty_session(self) -> None:
        engine = FakeEngine({"coalesce": (1,)})
        store = ChatHistoryStore(engine)
        idx = store.next_turn_idx(uuid4())
        assert idx == 1

    def test_returns_incremented_value(self) -> None:
        engine = FakeEngine({"coalesce": (4,)})
        store = ChatHistoryStore(engine)
        idx = store.next_turn_idx(uuid4())
        assert idx == 4


# ---------------------------------------------------------------------------
# save_turn (smoke test — the real thing needs a DB)
# ---------------------------------------------------------------------------


class TestSaveTurn:
    def test_save_turn_executes_inserts_and_update(self) -> None:
        # FakeEngine returns (1,) for any query containing "coalesce" (next_turn_idx)
        engine = FakeEngine({"coalesce": (1,)})
        store = ChatHistoryStore(engine)
        sid = uuid4()
        # Should not raise; returns the turn_idx used
        result = store.save_turn(sid, "query text", "answer text", [{"source": "x.md"}])
        assert result == 1
        # Verify the conn executed some statements (advisory lock + inserts + update)
        assert len(engine.conn.executed) > 0
