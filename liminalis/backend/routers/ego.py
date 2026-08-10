"""Ego API routes: auth, chat, records, roles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.domain_errors import DomainError
from backend._shared.storage import get_business_session
from backend.ego.auth_deps import require_ego_auth
from backend.ego.schemas.auth import PinLoginRequest
from backend.ego.schemas.chat import (
    ChatMessageResponse,
    CreateSessionRequest,
    SendMessageRequest,
    SessionResponse,
)
from backend.ego.schemas.record import CreateRecordRequest, RecordResponse
from backend.ego.schemas.role import UpdateCurrentRoleRequest
from backend.services import ego_service
from backend.settings import Settings, get_settings

router = APIRouter(prefix="/api/ego", tags=["ego"])


def _raise_domain_error(exc: DomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# ── Auth ────────────────────────────────────────────────────────────────────


@router.post("/auth/pin-login")
async def auth_pin_login(
    payload: PinLoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_business_session),
) -> dict:
    client_ip = request.client.host if request.client else "127.0.0.1"
    return await ego_service.pin_login(payload.pin, client_ip, settings, session)


# ── Roles ───────────────────────────────────────────────────────────────────


@router.get("/roles")
def get_roles() -> list[dict]:
    return ego_service.list_roles()


@router.get("/roles/current")
async def get_current_role(user_id: str = Depends(require_ego_auth)) -> dict:
    role = await ego_service.get_current_role(user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.put("/roles/current")
async def put_current_role(
    payload: UpdateCurrentRoleRequest,
    user_id: str = Depends(require_ego_auth),
) -> dict:
    ok = await ego_service.update_current_role(user_id, payload.role_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")
    return {"role_id": payload.role_id}


# ── Chat ────────────────────────────────────────────────────────────────────


@router.post("/chat/sessions")
async def create_chat_session(
    payload: CreateSessionRequest,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> SessionResponse:
    return await ego_service.create_chat_session(user_id, payload.role_id, session)


@router.get("/chat/sessions")
async def list_chat_sessions(
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> list[SessionResponse]:
    return await ego_service.list_chat_sessions(user_id, session)


@router.post("/chat/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: str,
    payload: SendMessageRequest,
    user_id: str = Depends(require_ego_auth),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await ego_service.send_chat_message(user_id, session_id, payload.content, settings)
    except DomainError as exc:
        _raise_domain_error(exc)


@router.get("/chat/sessions/{session_id}/messages")
async def list_chat_messages(
    session_id: str,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> list[ChatMessageResponse]:
    try:
        return await ego_service.list_chat_messages(user_id, session_id, session)
    except DomainError as exc:
        _raise_domain_error(exc)


# ── Records ─────────────────────────────────────────────────────────────────


@router.post("/records")
async def create_record(
    payload: CreateRecordRequest,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> RecordResponse:
    return await ego_service.create_record(user_id, payload, session)


@router.get("/records")
async def list_records(
    request: Request,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> dict:
    page = int(request.query_params.get("page", "1"))
    size = int(request.query_params.get("size", "20"))
    record_date = request.query_params.get("record_date")
    return await ego_service.list_records(user_id, session, page=page, size=size, record_date=record_date)


@router.get("/records/timeline")
async def get_timeline(
    request: Request,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> dict:
    month = request.query_params.get("month") or ""
    days = await ego_service.get_timeline(user_id, month, session)
    return {"days": [d.model_dump() for d in days]}


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> RecordResponse:
    record = await ego_service.get_record(record_id, user_id, session)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return record


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: str,
    user_id: str = Depends(require_ego_auth),
    session: AsyncSession = Depends(get_business_session),
) -> dict:
    deleted = await ego_service.delete_record(record_id, user_id, session)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return {"ok": True}
