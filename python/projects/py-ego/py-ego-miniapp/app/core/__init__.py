"""Core module for LLM, embeddings, and role management.

This module contains components adapted from py-ego core for use
in the FastAPI backend:
- llm_client: Async LLM client for chat completions
- embeddings: Async embedding generation
- role: Role models and definitions
- role_manager: Role management with relationship tracking
"""

from app.core.llm_client import LLMClient, chat_completion
from app.core.embeddings import get_embedding, get_embeddings_batch

__all__ = [
    "LLMClient",
    "chat_completion",
    "get_embedding",
    "get_embeddings_batch",
]
