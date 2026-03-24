"""Chat service for session and message management.

This module provides the ChatService class that handles:
- Creating and managing chat sessions
- Sending and receiving messages
- Paginated message retrieval
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession, User
from app.schemas import MessageCreate, SessionCreate
from app.utils import NotFoundException


class ChatService:
    """Service handling chat session and message operations.

    This service manages all chat-related operations for users:
    - Create and manage chat sessions
    - Send and receive messages
    - Retrieve messages with pagination
    - Delete sessions

    Attributes:
        _db: SQLAlchemy async session for database operations.
        _user: The authenticated user performing operations.
    """

    def __init__(self, db: AsyncSession, user: User):
        """Initialize the chat service.

        Args:
            db: SQLAlchemy async session for database operations.
            user: The authenticated user performing operations.
        """
        self._db = db
        self._user = user

    async def create_session(self, data: SessionCreate) -> ChatSession:
        """Create a new chat session.

        Creates a new chat session for the user with the specified AI role.

        Args:
            data: Session creation data containing role_id.

        Returns:
            ChatSession: The newly created session instance.
        """
        session = ChatSession(
            user_id=self._user.id,
            role_id=data.role_id,
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def get_sessions(
        self,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ChatSession], int]:
        """Get paginated chat sessions for the current user.

        Retrieves sessions ordered by most recent first.

        Args:
            page: Page number (1-indexed).
            size: Number of sessions per page.

        Returns:
            tuple[list[ChatSession], int]: A tuple containing:
                - list[ChatSession]: The paginated list of sessions.
                - int: Total count of sessions.
        """
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == self._user.id)
            .order_by(ChatSession.started_at.desc())
        )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.offset((page - 1) * size).limit(size)
        result = await self._db.execute(query)
        sessions = result.scalars().all()

        return list(sessions), total

    async def get_session(self, session_id: UUID) -> ChatSession:
        """Get a single chat session by ID.

        Retrieves a specific session ensuring it belongs to the current user.

        Args:
            session_id: UUID of the session to retrieve.

        Returns:
            ChatSession: The requested session instance.

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        result = await self._db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == self._user.id,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundException("Chat session not found")

        return session

    async def end_session(self, session_id: UUID) -> ChatSession:
        """End a chat session.

        Marks the session as ended by setting the ended_at timestamp.

        Args:
            session_id: UUID of the session to end.

        Returns:
            ChatSession: The updated session instance.

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        session = await self.get_session(session_id)
        session.ended_at = datetime.utcnow()
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def send_message(
        self,
        session_id: UUID,
        data: MessageCreate,
    ) -> tuple[str, int]:
        """Send a message and get a reply.

        Stores the user message and generates a reply.
        Currently returns an echo response; LLM integration to be added.

        Args:
            session_id: UUID of the session to send the message to.
            data: Message creation data containing the content.

        Returns:
            tuple[str, int]: A tuple containing:
                - str: The assistant's reply.
                - int: Number of memories used (0 for now).

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        # Verify session exists
        await self.get_session(session_id)

        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=data.content,
        )
        self._db.add(user_msg)

        # TODO: Call LLM service for actual reply
        # For now, return a placeholder response
        reply = f"[Echo] {data.content}"

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        self._db.add(assistant_msg)

        await self._db.commit()

        return reply, 0  # reply, memories_used

    async def get_messages(
        self,
        session_id: UUID,
        before: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[ChatMessage], bool]:
        """Get messages for a session with cursor-based pagination.

        Retrieves messages in reverse chronological order (newest first).

        Args:
            session_id: UUID of the session to retrieve messages from.
            before: Optional cursor - UUID of message to paginate before.
            limit: Maximum number of messages to return.

        Returns:
            tuple[list[ChatMessage], bool]: A tuple containing:
                - list[ChatMessage]: The list of messages.
                - bool: Whether there are more messages available.

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        await self.get_session(session_id)  # Verify access

        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
        )

        if before:
            before_msg = await self._db.execute(
                select(ChatMessage).where(ChatMessage.id == before)
            )
            before_msg = before_msg.scalar_one_or_none()
            if before_msg:
                query = query.where(ChatMessage.created_at < before_msg.created_at)

        query = query.limit(limit + 1)  # Fetch one extra to check has_more
        result = await self._db.execute(query)
        messages = list(result.scalars().all())

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        return messages, has_more

    async def delete_session(self, session_id: UUID) -> None:
        """Delete a chat session and its messages.

        Removes the session from the database. Messages are automatically
        deleted via cascade.

        Args:
            session_id: UUID of the session to delete.

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        session = await self.get_session(session_id)
        await self._db.delete(session)
        await self._db.commit()