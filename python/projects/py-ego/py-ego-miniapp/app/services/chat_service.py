"""Chat service for session and message management.

This module provides the ChatService class that handles:
- Creating and managing chat sessions
- Sending and receiving messages with LLM integration
- Semantic memory retrieval for context-aware responses
- Paginated message retrieval
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_client import LLMClient
from app.models import ChatMessage, ChatSession, User
from app.schemas import MessageCreate, SessionCreate
from app.services.memory_service import MemoryService
from app.services.role_service import role_service
from app.utils import NotFoundException


# Default system prompt for the AI assistant (fallback when no role is specified)
DEFAULT_SYSTEM_PROMPT = """你是一个温暖、专业的AI助手，专注于帮助用户记录生活、整理思绪和提供情感支持。

你的特点：
- 善于倾听，理解用户的情绪和感受
- 回答简洁、真诚，避免说教
- 能够记住用户之前分享的内容，建立连贯的对话
- 用中文回复用户

在回复时，请参考相关的记忆来提供个性化的回应。"""


class ChatService:
    """Service handling chat session and message operations with LLM integration.

    This service manages all chat-related operations for users:
    - Create and manage chat sessions
    - Send messages and generate AI responses using LLM
    - Retrieve relevant memories for context-aware responses
    - Paginated message retrieval
    - Delete sessions

    Attributes:
        _db: SQLAlchemy async session for database operations.
        _user: The authenticated user performing operations.
        _llm_client: Async LLM client for generating responses.
        _memory_service: Service for semantic memory operations.
    """

    def __init__(self, db: AsyncSession, user: User):
        """Initialize the chat service.

        Args:
            db: SQLAlchemy async session for database operations.
            user: The authenticated user performing operations.
        """
        self._db = db
        self._user = user
        self._llm_client = LLMClient()
        self._memory_service = MemoryService(db, user)

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
        """Send a message and get an AI reply.

        Stores the user message, retrieves relevant memories for context,
        generates an AI response using the LLM, and stores the reply.

        Args:
            session_id: UUID of the session to send the message to.
            data: Message creation data containing the content.

        Returns:
            tuple[str, int]: A tuple containing:
                - str: The assistant's reply.
                - int: Number of memories used for context.

        Raises:
            NotFoundException: If the session doesn't exist or doesn't belong
                              to the current user.
        """
        # Verify session exists
        session = await self.get_session(session_id)

        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=data.content,
        )
        self._db.add(user_msg)
        await self._db.commit()

        # Search for relevant memories
        memories = await self._memory_service.search_memories(data.content, k=5)
        memories_used = len(memories)

        # Build conversation context
        messages = await self._build_context(session_id, data.content, memories)

        # Generate AI response
        try:
            reply = await self._llm_client.chat_completion(
                messages,
                temperature=0.8,
                max_tokens=2048,
            )
        except Exception:
            # Fallback response if LLM fails
            reply = "抱歉，我暂时无法回应。请稍后再试。"

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        self._db.add(assistant_msg)
        await self._db.commit()

        # Store this conversation as memory
        memory_content = f"用户说: {data.content}\n助手回复: {reply}"
        await self._memory_service.add_memory(
            content=memory_content,
            source_type="chat",
        )

        return reply, memories_used

    async def _build_context(
        self,
        session_id: UUID,
        current_message: str,
        memories: list,
    ) -> list[dict[str, str]]:
        """Build the conversation context for the LLM.

        Constructs a message list including system prompt, relevant memories,
        and recent conversation history.

        Args:
            session_id: UUID of the current session.
            current_message: The user's current message.
            memories: List of relevant Memory objects.

        Returns:
            list[dict[str, str]]: List of message dicts for the LLM.
        """
        messages: list[dict[str, str]] = []

        # Get session to determine role
        session = await self.get_session(session_id)

        # Build memory context for relationship context
        memory_context = ""
        if memories:
            memory_context = "\n\n相关记忆:\n" + "\n".join(
                f"- {m.content}" for m in memories
            )

        # Get role-specific system prompt
        system_prompt = role_service.get_system_prompt(
            session.role_id,
            relationship_context=memory_context,
        )

        messages.append({"role": "system", "content": system_prompt})

        # Add recent conversation history (last 10 messages)
        recent_messages = await self._get_recent_messages(session_id, limit=10)
        for msg in reversed(recent_messages):  # Oldest first
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add current message (if not already in history)
        if not recent_messages or recent_messages[0].content != current_message:
            messages.append({"role": "user", "content": current_message})

        return messages

    async def _get_recent_messages(
        self,
        session_id: UUID,
        limit: int = 10,
    ) -> list[ChatMessage]:
        """Get recent messages from a session.

        Args:
            session_id: UUID of the session.
            limit: Maximum number of messages to retrieve.

        Returns:
            list[ChatMessage]: Recent messages, newest first.
        """
        result = await self._db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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
