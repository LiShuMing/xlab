"""Ego chat pipeline with explicit persistence and LLM boundaries."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from backend._shared.domain_errors import DomainNotFoundError
from backend._shared.llm import ChatMessage, get_llm_client
from backend._shared.serializers import utc_now, utc_timestamp_z
from backend._shared.storage import business_uow
from backend.ego.db_models import EgoMessage, EgoSession
from backend.ego.memory_profile_store import EgoMemoryHit, EgoMemoryRepository, EgoProfileRepository
from backend.ego.roles.role import PREDEFINED_ROLES, Role
from backend.settings import Settings


@dataclass(frozen=True)
class PersistedChatMessage:
    """A message persisted in the business database."""

    id: str
    role: str
    content: str
    created_at: str
    role_id: str | None = None
    role_label: str | None = None

    def to_response(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "role": self.role,
            "role_id": self.role_id,
            "role_label": self.role_label,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ChatTurnContext:
    """Context assembled before the slow LLM step."""

    user_message: PersistedChatMessage
    role_id: str
    history: list[dict[str, str]]


class EgoChatGraphState(TypedDict):
    user_id: str
    session_id: str
    content: str
    user_message: NotRequired[PersistedChatMessage]
    role_id: NotRequired[str]
    role: NotRequired[Role]
    history: NotRequired[list[dict[str, str]]]
    memories: NotRequired[list[EgoMemoryHit]]
    profile: NotRequired[str]
    reply_text: NotRequired[str]
    assistant_message: NotRequired[PersistedChatMessage]
    result: NotRequired[dict]


class EgoChatPipeline:
    """Orchestrates one Ego chat turn.

    The pipeline keeps the slow LLM call outside database transactions. This
    makes user-message persistence durable even if the client disconnects or
    the model provider is slow.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._memory_repo = EgoMemoryRepository(settings)
        self._profile_repo = EgoProfileRepository(settings)
        self._graph = self._build_graph()

    async def run(self, *, user_id: str, session_id: str, content: str) -> dict:
        started_at = perf_counter()
        state = await self._graph.ainvoke(
            {"user_id": user_id, "session_id": session_id, "content": content},
            config={"configurable": {"thread_id": session_id}},
        )
        self._logger.info(
            "ego chat turn completed",
            extra={
                "session_id": session_id,
                "role_id": state.get("role_id"),
                "history_count": len(state.get("history", [])),
                "memory_count": len(state.get("memories", [])),
                "elapsed_seconds": round(perf_counter() - started_at, 3),
            },
        )
        return state["result"]

    def _build_graph(self):
        builder = StateGraph(EgoChatGraphState)
        builder.add_node("persist_user_and_load_history", self._persist_user_message_and_load_context)
        builder.add_node("retrieve_context", self._retrieve_context)
        builder.add_node("generate_reply", self._generate_reply)
        builder.add_node("persist_assistant", self._persist_assistant_message)
        builder.add_node("learn", self._learn_from_turn)
        builder.add_edge(START, "persist_user_and_load_history")
        builder.add_edge("persist_user_and_load_history", "retrieve_context")
        builder.add_edge("retrieve_context", "generate_reply")
        builder.add_edge("generate_reply", "persist_assistant")
        builder.add_edge("persist_assistant", "learn")
        builder.add_edge("learn", END)
        return builder.compile(name="ego_chat_pipeline")

    async def _persist_user_message_and_load_context(
        self,
        state: EgoChatGraphState,
    ) -> dict:
        user_id = state["user_id"]
        session_id = state["session_id"]
        content = state["content"]
        async with business_uow() as session:
            result = await session.execute(
                select(EgoSession).where(EgoSession.id == session_id, EgoSession.user_id == user_id)
            )
            chat_session = result.scalar_one_or_none()
            if chat_session is None:
                raise DomainNotFoundError("chat session not found")

            user_msg_id = uuid.uuid4().hex
            user_created_at = utc_now()
            session.add(
                EgoMessage(
                    id=user_msg_id,
                    session_id=session_id,
                    role="user",
                    content=content,
                    created_at=user_created_at,
                )
            )
            chat_session.updated_at = user_created_at

            history_result = await session.execute(
                select(EgoMessage)
                .where(EgoMessage.session_id == session_id, EgoMessage.id != user_msg_id)
                .order_by(EgoMessage.created_at.desc())
                .limit(self._settings.ego_chat_history_limit)
            )
            history_rows = list(reversed(history_result.scalars().all()))

            return {
                "user_message": PersistedChatMessage(
                    id=user_msg_id,
                    role="user",
                    content=content,
                    created_at=utc_timestamp_z(user_created_at),
                ),
                "role_id": chat_session.role_id,
                "history": [{"role": row.role, "content": row.content} for row in history_rows],
            }

    async def _retrieve_context(self, state: EgoChatGraphState) -> dict:
        role_id = state.get("role_id") or "therapist"
        role = PREDEFINED_ROLES.get(role_id) or PREDEFINED_ROLES["therapist"]
        memories, profile = await asyncio.gather(
            self._memory_repo.search(user_id=state["user_id"], role_id=role.id, query=state["content"]),
            self._profile_repo.get_combined(user_id=state["user_id"], role_id=role.id),
        )
        return {"role": role, "role_id": role.id, "memories": memories, "profile": profile}

    async def _generate_reply(self, state: EgoChatGraphState) -> dict:
        role = state["role"]
        messages = self._build_llm_messages(
            role=role,
            user_input=state["content"],
            history=state.get("history", []),
            memories=state.get("memories", []),
            profile=state.get("profile", ""),
        )
        response = await get_llm_client(self._settings).complete(
            messages,
            model=self._settings.llm_model,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )
        return {"reply_text": response.text}

    async def _persist_assistant_message(self, state: EgoChatGraphState) -> dict:
        user_id = state["user_id"]
        session_id = state["session_id"]
        content = state["reply_text"]
        role = state["role"]
        async with business_uow() as session:
            result = await session.execute(
                select(EgoSession).where(EgoSession.id == session_id, EgoSession.user_id == user_id)
            )
            chat_session = result.scalar_one_or_none()
            if chat_session is None:
                raise DomainNotFoundError("chat session not found")

            assistant_msg_id = uuid.uuid4().hex
            assistant_created_at = utc_now()
            session.add(
                EgoMessage(
                    id=assistant_msg_id,
                    session_id=session_id,
                    role="assistant",
                    role_id=role.id,
                    role_label=role.name,
                    content=content,
                    created_at=assistant_created_at,
                )
            )
            chat_session.updated_at = assistant_created_at

            assistant_message = PersistedChatMessage(
                id=assistant_msg_id,
                role="assistant",
                role_id=role.id,
                role_label=role.name,
                content=content,
                created_at=utc_timestamp_z(assistant_created_at),
            )
            return {
                "assistant_message": assistant_message,
                "result": {
                    "user_message": state["user_message"].to_response(),
                    "reply": assistant_message.to_response(),
                },
            }

    async def _learn_from_turn(self, state: EgoChatGraphState) -> dict:
        role = state["role"]
        try:
            await self._memory_repo.add(
                user_id=state["user_id"],
                role_id=role.id,
                text=state["content"],
                meta={"source": "chat", "session_id": state["session_id"]},
            )
        except Exception:
            self._logger.exception("ego memory write failed")

        self._profile_repo.schedule_update_from_turn(
            user_id=state["user_id"],
            role_id=role.id,
            user_input=state["content"],
            assistant_reply=state["reply_text"],
        )
        return {}

    def _build_llm_messages(
        self,
        *,
        role: Role,
        user_input: str,
        history: list[dict[str, str]],
        memories: list[EgoMemoryHit],
        profile: str,
    ) -> list[ChatMessage]:
        messages = [ChatMessage(role="system", content=role.build_full_system_prompt(""))]
        examples = role.build_examples_context()
        if examples:
            messages.append(ChatMessage(role="system", content=examples))
        if profile:
            messages.append(ChatMessage(role="system", content=f"用户画像：\n{profile}"))
        if memories:
            memory_context = "\n".join(f"过去你曾说过：{memory.text}" for memory in memories)
            messages.append(ChatMessage(role="system", content=f"相关历史记忆:\n{memory_context}"))
        for item in history:
            messages.append(ChatMessage(role=item["role"], content=item["content"]))
        messages.append(ChatMessage(role="user", content=user_input))
        return messages
