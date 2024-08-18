"""
Session memory management for conversation history.

Provides utilities for storing and retrieving chat messages with
support for multiple concurrent conversations and context management.
"""

from dataclasses import dataclass, field
from typing import Self

import streamlit as st
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationContext:
    """Context information for a conversation."""
    session_id: str
    created_at: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    message_count: int = 0
    estimated_tokens: int = 0


class SessionMemoryManager(BaseChatMessageHistory):
    """
    Manages conversation memory using Streamlit session state.
    
    Supports multiple concurrent conversations with unique session keys.
    Implements BaseChatMessageHistory interface for LangChain compatibility.
    
    Attributes:
        session_key: Unique key for storing history in session state
        max_messages: Maximum number of messages to retain (None = unlimited)
    """
    
    def __init__(
        self,
        session_key: str = "chat_history",
        max_messages: int | None = None
    ):
        """
        Initialize memory manager with a session key.
        
        Args:
            session_key: Key for storing history in session state
            max_messages: Maximum number of messages to retain
        """
        self.session_key = session_key
        self.max_messages = max_messages
        self._ensure_initialized()
    
    def _ensure_initialized(self) -> None:
        """Ensure session state is initialized for this memory."""
        if self.session_key not in st.session_state:
            st.session_state[self.session_key] = []
            logger.debug("memory_initialized", session_key=self.session_key)
    
    @property
    def messages(self) -> list[BaseMessage]:
        """
        Get all messages in history (LangChain compatibility).
        
        Returns:
            List of messages
        """
        return self.get_history()
    
    @messages.setter
    def messages(self, value: list[BaseMessage]) -> None:
        """Set messages directly (LangChain compatibility)."""
        st.session_state[self.session_key] = value
    
    def add_message(self, message: BaseMessage) -> None:
        """
        Add a message to history (LangChain compatibility).
        
        Args:
            message: Message to add
        """
        self._ensure_initialized()
        st.session_state[self.session_key].append(message)
        
        # Enforce max_messages limit
        if self.max_messages and len(st.session_state[self.session_key]) > self.max_messages:
            st.session_state[self.session_key] = st.session_state[self.session_key][-self.max_messages:]
            logger.debug(
                "memory_trimmed",
                session_key=self.session_key,
                max_messages=self.max_messages
            )
    
    def add_user_message(self, content: str) -> None:
        """
        Add a human message to history.
        
        Args:
            content: Message content
        """
        self.add_message(HumanMessage(content=content))
        logger.debug("user_message_added", session_key=self.session_key, content_length=len(content))
    
    def add_ai_message(self, content: str) -> None:
        """
        Add an AI message to history.
        
        Args:
            content: Message content
        """
        self.add_message(AIMessage(content=content))
        logger.debug("ai_message_added", session_key=self.session_key, content_length=len(content))
    
    def add_system_message(self, content: str) -> None:
        """
        Add a system message to history.
        
        Args:
            content: Message content
        """
        self.add_message(SystemMessage(content=content))
        logger.debug("system_message_added", session_key=self.session_key)
    
    def get_history(self) -> list[BaseMessage]:
        """
        Get all messages in history.
        
        Returns:
            List of messages
        """
        self._ensure_initialized()
        return st.session_state.get(self.session_key, [])
    
    def clear(self) -> None:
        """Clear all messages from history."""
        st.session_state[self.session_key] = []
        logger.info("memory_cleared", session_key=self.session_key)
    
    def clear_history(self) -> None:
        """Alias for clear() for backward compatibility."""
        self.clear()
    
    def get_history_as_dicts(self) -> list[dict[str, str]]:
        """
        Convert history to list of dicts for display.
        
        Returns:
            List of {"role": str, "content": str} dicts.
            Roles: "user", "assistant", "system"
        """
        result: list[dict[str, str]] = []
        for msg in self.get_history():
            match msg:
                case HumanMessage():
                    result.append({"role": "user", "content": msg.content})
                case AIMessage():
                    result.append({"role": "assistant", "content": msg.content})
                case SystemMessage():
                    result.append({"role": "system", "content": msg.content})
        return result
    
    def get_last_n_messages(self, n: int) -> list[BaseMessage]:
        """
        Get last N messages from history.
        
        Args:
            n: Number of messages to retrieve
            
        Returns:
            List of last N messages (or fewer if history is shorter)
        """
        history = self.get_history()
        return history[-n:] if n > 0 else history
    
    def get_context_summary(self) -> dict[str, int | str]:
        """
        Get summary of conversation context.
        
        Returns:
            Dictionary with message count, estimated tokens, etc.
        """
        history = self.get_history()
        total_chars = sum(len(msg.content) for msg in history)
        
        return {
            "session_key": self.session_key,
            "message_count": len(history),
            "estimated_tokens": total_chars // 4,
            "user_messages": sum(1 for m in history if isinstance(m, HumanMessage)),
            "ai_messages": sum(1 for m in history if isinstance(m, AIMessage)),
        }
    
    def get_token_estimate(self) -> int:
        """
        Rough estimate of token count in history.
        
        Uses simple heuristic: ~4 characters per token.
        
        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.content) for msg in self.get_history())
        return total_chars // 4


def get_or_create_memory(
    session_key: str = "chat_history",
    max_messages: int | None = None
) -> SessionMemoryManager:
    """
    Get or create a memory manager for the given session key.
    
    Uses Streamlit session state to persist the manager instance.
    
    Args:
        session_key: Unique key for the conversation
        max_messages: Maximum messages to retain
    
    Returns:
        SessionMemoryManager instance
    
    Example:
        >>> memory = get_or_create_memory("my_chat")
        >>> memory.add_user_message("Hello")
        >>> history = memory.get_history()
    """
    manager_key = f"memory_manager_{session_key}"
    
    if manager_key not in st.session_state:
        st.session_state[manager_key] = SessionMemoryManager(
            session_key=session_key,
            max_messages=max_messages
        )
        logger.debug("memory_manager_created", session_key=session_key)
    
    return st.session_state[manager_key]


def clear_all_memories() -> None:
    """Clear all memory managers from session state."""
    keys_to_clear = [
        key for key in st.session_state.keys()
        if key.startswith("memory_manager_") or key == "chat_history"
    ]
    for key in keys_to_clear:
        del st.session_state[key]
    
    logger.info("all_memories_cleared", count=len(keys_to_clear))
