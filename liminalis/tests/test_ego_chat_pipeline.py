"""Unit tests for the Ego chat pipeline boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from backend.ego.chat_pipeline import EgoChatPipeline
from backend.ego.db_models import EgoMessage
from backend.ego.memory_profile_store import EgoMemoryHit
from backend.settings import Settings


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _ExecuteResult:
    def __init__(self, *, scalar: object | None = None, rows: list[object] | None = None) -> None:
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self._scalar

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._rows)


class _FakeSession:
    def __init__(self, results: list[_ExecuteResult]) -> None:
        self._results = results
        self.added: list[object] = []

    async def execute(self, _statement: object) -> _ExecuteResult:
        return self._results.pop(0)

    def add(self, row: object) -> None:
        self.added.append(row)


class _FakeMemoryRepo:
    def __init__(self) -> None:
        self.added: list[dict] = []

    async def search(self, *, user_id: str, role_id: str, query: str, limit: int | None = None):
        assert user_id == "user-1"
        assert role_id == "therapist"
        assert query == "今天有点累"
        return [EgoMemoryHit(text="用户之前说过最近睡眠不太稳定。", score=0.1)]

    async def add(self, **kwargs) -> None:
        self.added.append(kwargs)


class _FakeProfileRepo:
    def __init__(self) -> None:
        self.scheduled: list[dict] = []

    async def get_combined(self, *, user_id: str, role_id: str) -> str:
        assert user_id == "user-1"
        assert role_id == "therapist"
        return "用户偏好温和、直接的建议。"

    def schedule_update_from_turn(self, **kwargs) -> None:
        self.scheduled.append(kwargs)


class _FakeLLMClient:
    def __init__(self) -> None:
        self.messages = None

    async def complete(self, messages, **_kwargs):
        self.messages = messages
        return type("Response", (), {"text": "我在，先慢慢来。"})()


@pytest.mark.asyncio
async def test_chat_pipeline_persists_user_before_llm_and_reply_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_session = type("ChatSession", (), {"id": "session-1", "user_id": "user-1", "role_id": "therapist"})()
    previous_message = EgoMessage(
        id="previous",
        session_id="session-1",
        role="assistant",
        content="上次我们聊到休息。",
        created_at=datetime(2026, 6, 7, tzinfo=UTC),
    )
    first_session = _FakeSession(
        [
            _ExecuteResult(scalar=chat_session),
            _ExecuteResult(rows=[previous_message]),
        ]
    )
    second_session = _FakeSession([_ExecuteResult(scalar=chat_session)])
    opened_sessions: list[_FakeSession] = []

    @asynccontextmanager
    async def fake_uow():
        session = [first_session, second_session][len(opened_sessions)]
        opened_sessions.append(session)
        yield session

    fake_llm = _FakeLLMClient()

    monkeypatch.setattr("backend.ego.chat_pipeline.business_uow", fake_uow)
    monkeypatch.setattr("backend.ego.chat_pipeline.get_llm_client", lambda _settings: fake_llm)

    pipeline = EgoChatPipeline(Settings(llm_api_key="test-key"))
    fake_memory_repo = _FakeMemoryRepo()
    fake_profile_repo = _FakeProfileRepo()
    pipeline._memory_repo = fake_memory_repo
    pipeline._profile_repo = fake_profile_repo

    result = await pipeline.run(
        user_id="user-1",
        session_id="session-1",
        content="今天有点累",
    )

    assert len(opened_sessions) == 2
    assert first_session.added[0].role == "user"
    assert first_session.added[0].content == "今天有点累"
    assert second_session.added[0].role == "assistant"
    assert second_session.added[0].content == "我在，先慢慢来。"
    assert any("用户偏好温和" in message.content for message in fake_llm.messages)
    assert any("睡眠不太稳定" in message.content for message in fake_llm.messages)
    assert fake_memory_repo.added[0]["text"] == "今天有点累"
    assert fake_profile_repo.scheduled[0]["assistant_reply"] == "我在，先慢慢来。"
    assert result["user_message"]["role"] == "user"
    assert result["reply"]["role_id"] == "therapist"
    assert result["reply"]["content"] == "我在，先慢慢来。"
