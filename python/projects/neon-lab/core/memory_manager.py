"""
Session memory management for conversation history.
Provides utilities for storing and retrieving chat messages.
"""

from typing import List, Optional, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.chat_history import BaseChatMessageHistory
import streamlit as st


class SessionMemoryManager:
    """
    Manages conversation memory using Streamlit session state.
    Supports multiple concurrent conversations.
    """
    
    def __init__(self, session_key: str = "chat_history"):
        """
        Initialize memory manager with a session key.
        
        Args:
            session_key: Key for storing history in session state.
        """
        self.session_key = session_key
        if session_key not in st.session_state:
            st.session_state[session_key] = []
    
    def add_user_message(self, content: str) -> None:
        """Add a human message to history."""
        st.session_state[self.session_key].append(
            HumanMessage(content=content)
        )
    
    def add_ai_message(self, content: str) -> None:
        """Add an AI message to history."""
        st.session_state[self.session_key].append(
            AIMessage(content=content)
        )
    
    def add_system_message(self, content: str) -> None:
        """Add a system message to history."""
        st.session_state[self.session_key].append(
            SystemMessage(content=content)
        )
    
    def get_history(self) -> List[BaseMessage]:
        """Get all messages in history."""
        return st.session_state.get(self.session_key, [])
    
    def clear_history(self) -> None:
        """Clear all messages from history."""
        st.session_state[self.session_key] = []
    
    def get_history_as_dicts(self) -> List[Dict[str, str]]:
        """
        Convert history to list of dicts for display.
        
        Returns:
            List of {"role": str, "content": str} dicts.
        """
        result = []
        for msg in self.get_history():
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
        return result
    
    def get_last_n_messages(self, n: int) -> List[BaseMessage]:
        """Get last N messages from history."""
        history = self.get_history()
        return history[-n:] if n > 0 else history
    
    def get_token_estimate(self) -> int:
        """
        Rough estimate of token count in history.
        Simple heuristic: ~4 characters per token.
        
        Returns:
            Estimated token count.
        """
        total_chars = sum(len(msg.content) for msg in self.get_history())
        return total_chars // 4


def get_or_create_memory(session_key: str = "chat_history") -> SessionMemoryManager:
    """
    Get or create a memory manager for the given session key.
    
    Args:
        session_key: Unique key for the conversation.
    
    Returns:
        SessionMemoryManager instance.
    """
    manager_key = f"memory_manager_{session_key}"
    if manager_key not in st.session_state:
        st.session_state[manager_key] = SessionMemoryManager(session_key)
    return st.session_state[manager_key]
