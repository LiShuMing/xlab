"""Ego service: auth, chat, records, roles — driven by absorbed backend/ego/ code."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.auth import issue_access_token
from backend.ego.chat_registry import get_chat_service, switch_chat_role
from backend.ego.config import get_settings as get_ego_settings
from backend.ego.db_models import EgoMessage, EgoRecord, EgoSession
from backend.ego.roles.role import PREDEFINED_ROLES
from backend.ego.schemas.chat import ChatMessageResponse, SessionResponse
from backend.ego.schemas.record import CreateRecordRequest, RecordResponse, TimelineDay
from backend.settings import Settings


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ── Auth ────────────────────────────────────────────────────────────────────


async def pin_login(
    pin: str, client_ip: str, settings: Settings, session: AsyncSession
) -> dict:
    user_id = hashlib.sha256(f"{client_ip}:{pin}".encode()).hexdigest()[:16]
    token = issue_access_token(settings, user_id=user_id)
    return {"token": token, "user": {"id": user_id}}


# ── Roles ───────────────────────────────────────────────────────────────────


def list_roles() -> list[dict]:
    return [
        {"id": r.id, "name": r.name, "icon": r.icon, "description": r.description}
        for r in PREDEFINED_ROLES.values()
    ]


async def get_current_role(user_id: str) -> dict | None:
    svc = await get_chat_service(user_id)
    role = svc.current_role
    return {"id": role.id, "name": role.name, "icon": role.icon, "description": role.description}


async def update_current_role(user_id: str, role_id: str) -> bool:
    return await switch_chat_role(user_id, role_id)


# ── Chat ────────────────────────────────────────────────────────────────────


async def create_chat_session(
    user_id: str, role_id: str, session: AsyncSession
) -> SessionResponse:
    sid = uuid.uuid4().hex
    now = _now_iso()
    row = EgoSession(id=sid, user_id=user_id, role_id=role_id)
    session.add(row)
    await session.commit()
    return SessionResponse(id=sid, user_id=user_id, role_id=role_id, created_at=now, updated_at=now)


async def list_chat_sessions(
    user_id: str, session: AsyncSession
) -> list[SessionResponse]:
    result = await session.execute(
        select(EgoSession)
        .where(EgoSession.user_id == user_id)
        .order_by(EgoSession.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        SessionResponse(
            id=r.id,
            user_id=r.user_id,
            role_id=r.role_id,
            created_at=r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            updated_at=r.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for r in rows
    ]


async def send_chat_message(
    user_id: str,
    session_id: str,
    content: str,
    session: AsyncSession,
    settings: Settings | None = None,
) -> dict:
    svc = await get_chat_service(user_id)

    # Persist user message
    user_msg_id = uuid.uuid4().hex
    user_msg = EgoMessage(
        id=user_msg_id,
        session_id=session_id,
        role="user",
        content=content,
        created_at=datetime.now(UTC),
    )
    session.add(user_msg)

    # Update session timestamp
    await session.execute(
        text("UPDATE ego_sessions SET updated_at = now() WHERE id = :sid"),
        {"sid": session_id},
    )

    # Load recent conversation history for context
    ego_settings = get_ego_settings()
    history_limit = ego_settings.chat_history_limit
    history_result = await session.execute(
        select(EgoMessage)
        .where(EgoMessage.session_id == session_id)
        .order_by(EgoMessage.created_at.desc())
        .limit(history_limit)
    )
    history = [
        {"role": r.role, "content": r.content}
        for r in reversed(history_result.scalars().all())
    ]

    # Generate LLM reply
    reply_text = await _call_chat_service(svc, content, history)
    role = svc.current_role

    # Persist assistant message
    assistant_msg_id = uuid.uuid4().hex
    assistant_msg = EgoMessage(
        id=assistant_msg_id,
        session_id=session_id,
        role="assistant",
        role_id=role.id,
        role_label=role.name,
        content=reply_text,
        created_at=datetime.now(UTC),
    )
    session.add(assistant_msg)
    await session.commit()

    return {
        "user_message": {
            "id": user_msg_id,
            "role": "user",
            "content": content,
            "created_at": user_msg.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "reply": {
            "id": assistant_msg_id,
            "role": "assistant",
            "role_id": role.id,
            "role_label": role.name,
            "content": reply_text,
            "created_at": assistant_msg.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


async def _call_chat_service(svc, content: str, history: list[dict[str, str]] | None = None) -> str:
    import asyncio as _asyncio

    return await _asyncio.to_thread(svc.chat, content, history)


async def list_chat_messages(
    session_id: str, db_session: AsyncSession
) -> list[ChatMessageResponse]:
    result = await db_session.execute(
        select(EgoMessage)
        .where(EgoMessage.session_id == session_id)
        .order_by(EgoMessage.created_at)
    )
    rows = result.scalars().all()
    return [
        ChatMessageResponse(
            id=r.id,
            role=r.role,
            role_id=r.role_id,
            role_label=r.role_label,
            content=r.content,
            created_at=r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for r in rows
    ]


# ── Records ─────────────────────────────────────────────────────────────────


async def create_record(
    user_id: str, payload: CreateRecordRequest, db_session: AsyncSession
) -> RecordResponse:
    rid = uuid.uuid4().hex
    now = _now_iso()
    row = EgoRecord(
        id=rid,
        user_id=user_id,
        content_type=payload.content_type,
        content=payload.content,
        media_url=payload.media_url,
        record_date=_today(),
    )
    db_session.add(row)
    await db_session.commit()
    return RecordResponse(
        id=rid,
        content_type=payload.content_type,
        content=payload.content,
        media_url=payload.media_url,
        record_date=_today(),
        created_at=now,
    )


async def list_records(
    user_id: str,
    db_session: AsyncSession,
    *,
    page: int = 1,
    size: int = 20,
    record_date: str | None = None,
) -> dict:
    q = select(EgoRecord).where(EgoRecord.user_id == user_id)
    if record_date:
        q = q.where(EgoRecord.record_date == record_date)
    q = q.order_by(EgoRecord.created_at.desc())

    # Count
    count_q = select(func.count()).select_from(EgoRecord).where(EgoRecord.user_id == user_id)
    if record_date:
        count_q = count_q.where(EgoRecord.record_date == record_date)
    total = (await db_session.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * size
    result = await db_session.execute(q.offset(offset).limit(size))
    rows = result.scalars().all()

    items = [
        RecordResponse(
            id=r.id,
            content_type=r.content_type,
            content=r.content,
            media_url=r.media_url,
            record_date=r.record_date,
            created_at=r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "size": size}


async def get_record(
    record_id: str, user_id: str, db_session: AsyncSession
) -> RecordResponse | None:
    result = await db_session.execute(
        select(EgoRecord).where(
            EgoRecord.id == record_id, EgoRecord.user_id == user_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return RecordResponse(
        id=row.id,
        content_type=row.content_type,
        content=row.content,
        media_url=row.media_url,
        record_date=row.record_date,
        created_at=row.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


async def delete_record(
    record_id: str, user_id: str, db_session: AsyncSession
) -> bool:
    result = await db_session.execute(
        delete(EgoRecord).where(
            EgoRecord.id == record_id, EgoRecord.user_id == user_id
        )
    )
    await db_session.commit()
    return result.rowcount > 0


async def get_timeline(
    user_id: str, month: str, db_session: AsyncSession
) -> list[TimelineDay]:
    q = (
        select(
            EgoRecord.record_date,
            func.count().label("count"),
            func.max(EgoRecord.content).label("preview"),
        )
        .where(
            EgoRecord.user_id == user_id,
            EgoRecord.record_date.like(f"{month}%"),
        )
        .group_by(EgoRecord.record_date)
        .order_by(EgoRecord.record_date.desc())
    )
    result = await db_session.execute(q)
    rows = result.all()
    return [
        TimelineDay(
            date=row.record_date,
            count=row.count,
            preview=(row.preview or "")[:80],
        )
        for row in rows
    ]
