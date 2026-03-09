"""
Modern LLM Request Module

A refactored, type-safe, and extensible LLM provider system.
Supports: OpenAI, Anthropic (Claude), Qwen (Aliyun)

Example:
    >>> from request_llms import LLMFactory
    >>> llm = LLMFactory.create("gpt-4o")
    >>> response = await llm.chat([Message.user("Hello!")])

Migration from legacy API:
    >>> # Old way (still works)
    >>> from request_llms import predict, predict_no_ui_long_connection
    >>> 
    >>> # New way (recommended)
    >>> from request_llms import LLMFactory, Message
    >>> provider = LLMFactory.create("gpt-4o")
    >>> response = await provider.chat([Message.user("Hello!")])
"""

from .core import LLMFactory, LLMProvider, Message, ChatConfig, ChatResponse, Role
from .providers import OpenAIProvider, AnthropicProvider, QwenProvider
from .models import register_all_models, list_models_by_provider, get_model_info

# Backward compatibility
from .compat import predict, predict_no_ui_long_connection, get_available_models

# Auto-register models
register_all_models()

__version__ = "2.0.0"
__all__ = [
    # Core classes
    "LLMFactory",
    "LLMProvider",
    "Message",
    "ChatConfig",
    "ChatResponse",
    "Role",
    # Providers
    "OpenAIProvider",
    "AnthropicProvider",
    "QwenProvider",
    # Utilities
    "register_all_models",
    "list_models_by_provider",
    "get_model_info",
    "get_available_models",
    # Legacy compatibility
    "predict",
    "predict_no_ui_long_connection",
]
