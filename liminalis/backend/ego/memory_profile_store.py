"""Database-backed Ego memory and profile stores."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, cast, desc, literal, select
from sqlalchemy.dialects.postgresql import insert

from backend._shared.llm import ChatMessage, LLMError, get_llm_client
from backend._shared.serializers import utc_now
from backend._shared.storage import business_uow
from backend.ego.db_models import EgoMemory, EgoProfile
from backend.ego.embeddings import get_embedding
from backend.settings import Settings

GLOBAL_PROFILE_ROLE = "global"


@dataclass(frozen=True)
class EgoMemoryHit:
    text: str
    score: float


class EgoMemoryRepository:
    """Durable semantic memory backed by the business database."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    async def add(self, *, user_id: str, role_id: str, text: str, meta: dict[str, Any] | None = None) -> None:
        embedding = await asyncio.to_thread(get_embedding, text)
        async with business_uow() as session:
            session.add(
                EgoMemory(
                    id=uuid.uuid4().hex,
                    user_id=user_id,
                    role_id=role_id,
                    text=text,
                    embedding=[float(v) for v in embedding] if embedding is not None else None,
                    meta=meta or {},
                )
            )

    async def search(self, *, user_id: str, role_id: str, query: str, limit: int | None = None) -> list[EgoMemoryHit]:
        top_k = limit or self._settings.ego_chat_memory_top_k
        if top_k <= 0:
            return []

        embedding = await asyncio.to_thread(get_embedding, query)
        query_vector = [float(v) for v in embedding] if embedding is not None else None
        if not query_vector:
            return []

        async with business_uow() as session:
            distance_expr = EgoMemory.embedding.op("<->")(literal(query_vector, type_=Vector()))
            distance_value = cast(distance_expr, Float)
            result = await session.execute(
                select(EgoMemory.text, distance_value.label("distance"))
                .where(
                    EgoMemory.user_id == user_id,
                    EgoMemory.role_id == role_id,
                    EgoMemory.embedding.is_not(None),
                )
                .order_by(distance_expr)
                .limit(top_k)
            )
            return [EgoMemoryHit(text=row.text, score=float(row.distance)) for row in result.all()]

    async def latest(self, *, user_id: str, role_id: str, limit: int = 20) -> list[str]:
        async with business_uow() as session:
            result = await session.execute(
                select(EgoMemory.text)
                .where(EgoMemory.user_id == user_id, EgoMemory.role_id == role_id)
                .order_by(desc(EgoMemory.created_at))
                .limit(limit)
            )
            return [str(row[0]) for row in result.all()]


class EgoProfileRepository:
    """Durable profile store backed by the business database."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    async def get_combined(self, *, user_id: str, role_id: str) -> str:
        async with business_uow() as session:
            result = await session.execute(
                select(EgoProfile).where(
                    EgoProfile.user_id == user_id,
                    EgoProfile.role_id.in_([GLOBAL_PROFILE_ROLE, role_id]),
                )
            )
            rows = {row.role_id: row.content for row in result.scalars().all()}

        parts: list[str] = []
        global_profile = rows.get(GLOBAL_PROFILE_ROLE, "").strip()
        role_profile = rows.get(role_id, "").strip()
        if global_profile:
            parts.append("【全局画像】\n" + global_profile)
        if role_profile:
            parts.append("【角色画像】\n" + role_profile)
        return "\n\n".join(parts)

    async def upsert(self, *, user_id: str, role_id: str, content: str) -> None:
        row_id = self._row_id(user_id, role_id)
        stmt = insert(EgoProfile).values(
            id=row_id,
            user_id=user_id,
            role_id=role_id,
            content=content.strip(),
            updated_at=utc_now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ego_profiles_user_role",
            set_={"content": stmt.excluded.content, "updated_at": stmt.excluded.updated_at},
        )
        async with business_uow() as session:
            await session.execute(stmt)

    async def update_from_turn(
        self,
        *,
        user_id: str,
        role_id: str,
        user_input: str,
        assistant_reply: str,
    ) -> None:
        current_profile = await self.get_combined(user_id=user_id, role_id=role_id)
        prompt = self._build_update_prompt(current_profile, user_input, assistant_reply)
        client = get_llm_client(self._settings)
        try:
            response = await client.complete(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=500,
            )
        except LLMError as exc:
            self._logger.warning("ego profile update failed: %s", exc)
            return
        await self.upsert(user_id=user_id, role_id=role_id, content=response.text)

    def schedule_update_from_turn(
        self,
        *,
        user_id: str,
        role_id: str,
        user_input: str,
        assistant_reply: str,
    ) -> None:
        async def _run() -> None:
            try:
                await self.update_from_turn(
                    user_id=user_id,
                    role_id=role_id,
                    user_input=user_input,
                    assistant_reply=assistant_reply,
                )
            except Exception:
                self._logger.exception("ego profile background update crashed")

        asyncio.create_task(_run())

    def _build_update_prompt(self, current_profile: str, user_input: str, assistant_reply: str) -> str:
        return (
            "你是一个用户画像更新助手。请根据本轮对话，更新下方的用户画像。\n"
            "规则：\n"
            "1. 只记录用户明确说出的事实，不要推断或臆测\n"
            "2. 控制在300字以内\n"
            "3. 保留已有的准确信息，删除过时的信息\n"
            '4. 用第三人称描述（"用户..."）\n'
            "5. 如果已有信息较多，优先保留最近和最常出现的信息，适当压缩早期细节\n\n"
            f"当前画像：\n{current_profile}\n\n"
            f"本轮对话：\n用户：{user_input}\n助手：{assistant_reply}\n\n"
            "请输出更新后的用户画像（只输出画像内容，不要其他说明）："
        )

    def _row_id(self, user_id: str, role_id: str) -> str:
        return f"{user_id}:{role_id}"
