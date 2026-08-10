"""Ego service: auth, chat, records, roles — driven by absorbed backend/ego/ code."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.auth import issue_access_token
from backend._shared.domain_errors import DomainNotFoundError
from backend._shared.serializers import date_key, utc_timestamp_z
from backend.ego.chat_pipeline import EgoChatPipeline
from backend.ego.chat_registry import get_chat_service, switch_chat_role
from backend.ego.db_models import EgoMessage, EgoRecord, EgoSession
from backend.ego.roles.role import PREDEFINED_ROLES
from backend.ego.schemas.chat import ChatMessageResponse, SessionResponse
from backend.ego.schemas.record import CreateRecordRequest, RecordResponse, TimelineDay
from backend.settings import Settings, get_settings


def _now_iso() -> str:
    return utc_timestamp_z()


def _today() -> str:
    return date_key()


# ── Auth ────────────────────────────────────────────────────────────────────


async def pin_login(pin: str, client_ip: str, settings: Settings, session: AsyncSession) -> dict:
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


async def _get_owned_chat_session(user_id: str, session_id: str, db_session: AsyncSession) -> EgoSession:
    result = await db_session.execute(
        select(EgoSession).where(EgoSession.id == session_id, EgoSession.user_id == user_id)
    )
    chat_session = result.scalar_one_or_none()
    if chat_session is None:
        raise DomainNotFoundError("chat session not found")
    return chat_session


async def create_chat_session(user_id: str, role_id: str, session: AsyncSession) -> SessionResponse:
    sid = uuid.uuid4().hex
    now = _now_iso()
    row = EgoSession(id=sid, user_id=user_id, role_id=role_id)
    session.add(row)
    await session.flush()
    return SessionResponse(id=sid, user_id=user_id, role_id=role_id, created_at=now, updated_at=now)


async def list_chat_sessions(user_id: str, session: AsyncSession) -> list[SessionResponse]:
    result = await session.execute(
        select(EgoSession).where(EgoSession.user_id == user_id).order_by(EgoSession.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        SessionResponse(
            id=r.id,
            user_id=r.user_id,
            role_id=r.role_id,
            created_at=utc_timestamp_z(r.created_at),
            updated_at=utc_timestamp_z(r.updated_at),
        )
        for r in rows
    ]


async def send_chat_message(
    user_id: str,
    session_id: str,
    content: str,
    settings: Settings | None = None,
) -> dict:
    pipeline = EgoChatPipeline(settings or get_settings())
    return await pipeline.run(user_id=user_id, session_id=session_id, content=content)


async def list_chat_messages(
    user_id: str, session_id: str, db_session: AsyncSession
) -> list[ChatMessageResponse]:
    await _get_owned_chat_session(user_id, session_id, db_session)
    result = await db_session.execute(
        select(EgoMessage).where(EgoMessage.session_id == session_id).order_by(EgoMessage.created_at)
    )
    rows = result.scalars().all()
    return [
        ChatMessageResponse(
            id=r.id,
            role=r.role,
            role_id=r.role_id,
            role_label=r.role_label,
            content=r.content,
            created_at=utc_timestamp_z(r.created_at),
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
    await db_session.flush()
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
            created_at=utc_timestamp_z(r.created_at),
        )
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "size": size}


async def get_record(record_id: str, user_id: str, db_session: AsyncSession) -> RecordResponse | None:
    result = await db_session.execute(
        select(EgoRecord).where(EgoRecord.id == record_id, EgoRecord.user_id == user_id)
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
        created_at=utc_timestamp_z(row.created_at),
    )


async def delete_record(record_id: str, user_id: str, db_session: AsyncSession) -> bool:
    result = await db_session.execute(
        delete(EgoRecord).where(EgoRecord.id == record_id, EgoRecord.user_id == user_id)
    )
    await db_session.flush()
    return result.rowcount > 0


async def get_timeline(user_id: str, month: str, db_session: AsyncSession) -> list[TimelineDay]:
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
