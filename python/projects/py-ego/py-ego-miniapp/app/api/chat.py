"""Chat API routes for session and message management.

This module provides endpoints for:
- Creating and managing chat sessions
- Sending and receiving messages
- Listing sessions and messages
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas import (
    ChatReply,
    ErrorResponse,
    MessageCreate,
    PaginatedResponse,
    SessionCreate,
    SessionResponse,
    SuccessResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
    summary="Create chat session",
    description="Create a new chat session with a specific AI role",
)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create a new chat session.

    Creates a new chat session for the authenticated user with the specified
    AI role (e.g., 'therapist').

    Args:
        data: Session creation data with role_id.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        SessionResponse: The created session with ID and timestamps.
    """
    service = ChatService(db, current_user)
    session = await service.create_session(data)
    return session


@router.get(
    "/sessions",
    response_model=PaginatedResponse[SessionResponse],
    summary="List chat sessions",
    description="Retrieve paginated list of chat sessions for the authenticated user",
)
async def list_sessions(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[SessionResponse]:
    """List chat sessions with pagination.

    Retrieves sessions for the authenticated user, ordered by most recent first.

    Args:
        page: Page number (1-indexed).
        size: Number of sessions per page (max 100).
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        PaginatedResponse[SessionResponse]: Paginated list of sessions with total count.
    """
    service = ChatService(db, current_user)
    sessions, total = await service.get_sessions(page, size)
    return PaginatedResponse(items=sessions, total=total, page=page, size=size)


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Update chat session",
    description="Update a chat session (e.g., end the session)",
)
async def update_session(
    session_id: UUID,
    action: str = Query(..., pattern="^end$", description="Action to perform (only 'end' supported)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Update a chat session.

    Currently only supports ending a session by setting the ended_at timestamp.

    Args:
        session_id: UUID of the session to update.
        action: Action to perform (must be 'end').
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        SessionResponse: The updated session.

    Raises:
        NotFoundException: If session doesn't exist or doesn't belong to user.
    """
    service = ChatService(db, current_user)
    session = await service.end_session(session_id)
    return session


@router.delete(
    "/sessions/{session_id}",
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete chat session",
    description="Delete a chat session and all its messages",
)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse:
    """Delete a chat session.

    Removes the session and all associated messages from the database.

    Args:
        session_id: UUID of the session to delete.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        SuccessResponse: Confirmation of deletion.

    Raises:
        NotFoundException: If session doesn't exist or doesn't belong to user.
    """
    service = ChatService(db, current_user)
    await service.delete_session(session_id)
    return SuccessResponse()


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatReply,
    responses={404: {"model": ErrorResponse}},
    summary="Send message",
    description="Send a message in a chat session and receive a reply",
)
async def send_message(
    session_id: UUID,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatReply:
    """Send a message in a chat session.

    Stores the user message and returns the assistant's reply.
    Currently returns an echo response; LLM integration to be added.

    Args:
        session_id: UUID of the session to send the message to.
        data: Message data with content.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        ChatReply: The assistant's reply and memories used count.

    Raises:
        NotFoundException: If session doesn't exist or doesn't belong to user.
    """
    service = ChatService(db, current_user)
    reply, memories_used = await service.send_message(session_id, data)
    return ChatReply(reply=reply, memories_used=memories_used)


@router.get(
    "/sessions/{session_id}/messages",
    responses={404: {"model": ErrorResponse}},
    summary="List messages",
    description="Retrieve messages from a chat session with cursor-based pagination",
)
async def list_messages(
    session_id: UUID,
    before: Optional[UUID] = Query(None, description="Cursor - message UUID to paginate before"),
    limit: int = Query(50, ge=1, le=100, description="Maximum messages to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """List messages in a chat session.

    Retrieves messages in reverse chronological order (newest first).
    Supports cursor-based pagination using the 'before' parameter.

    Args:
        session_id: UUID of the session to retrieve messages from.
        before: Optional cursor - UUID of message to paginate before.
        limit: Maximum number of messages to return (max 100).
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        dict: Contains 'messages' list and 'has_more' boolean.

    Raises:
        NotFoundException: If session doesn't exist or doesn't belong to user.
    """
    service = ChatService(db, current_user)
    messages, has_more = await service.get_messages(session_id, before, limit)
    return {"messages": messages, "has_more": has_more}