"""
Backward compatibility bridge for legacy code.

This module provides a compatibility layer for code that imports from
the old request_llms.bridge_all module. It maps the old API to the new
modern provider architecture.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .compat import predict, predict_no_ui_long_connection
from .core import LLMFactory


def _create_compatible_model_entry(
    model_name: str,
    max_token: int = 4096,
    has_multimodal: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Create a model_info entry compatible with the legacy format."""
    
    def fn_with_ui(*args, **kwargs):
        """UI version - delegates to predict."""
        return predict(*args, **kwargs)
    
    def fn_without_ui(*args, **kwargs):
        """Non-UI version - delegates to predict_no_ui_long_connection."""
        return predict_no_ui_long_connection(*args, **kwargs)
    
    entry = {
        "fn_with_ui": fn_with_ui,
        "fn_without_ui": fn_without_ui,
        "endpoint": None,
        "max_token": max_token,
        "tokenizer": None,
        "token_cnt": lambda x: 0,  # Simplified token counter
    }
    
    if has_multimodal:
        entry["has_multimodal_capacity"] = True
    
    # Add any additional attributes
    entry.update(kwargs)
    return entry


# Model info dictionary for backward compatibility
# Maps model names to their configuration
model_info: Dict[str, Dict[str, Any]] = {
    # OpenAI Models
    "gpt-3.5-turbo": _create_compatible_model_entry("gpt-3.5-turbo", max_token=16385),
    "gpt-3.5-turbo-16k": _create_compatible_model_entry("gpt-3.5-turbo-16k", max_token=16385),
    "gpt-4": _create_compatible_model_entry("gpt-4", max_token=8192),
    "gpt-4-32k": _create_compatible_model_entry("gpt-4-32k", max_token=32768),
    "gpt-4-turbo": _create_compatible_model_entry("gpt-4-turbo", max_token=128000, has_multimodal=True),
    "gpt-4-turbo-preview": _create_compatible_model_entry("gpt-4-turbo-preview", max_token=128000),
    "gpt-4o": _create_compatible_model_entry("gpt-4o", max_token=128000, has_multimodal=True),
    "gpt-4o-mini": _create_compatible_model_entry("gpt-4o-mini", max_token=128000, has_multimodal=True),
    "gpt-4o-2024-05-13": _create_compatible_model_entry("gpt-4o-2024-05-13", max_token=128000, has_multimodal=True),
    "chatgpt-4o-latest": _create_compatible_model_entry("chatgpt-4o-latest", max_token=128000, has_multimodal=True),
    "gpt-4.1": _create_compatible_model_entry("gpt-4.1", max_token=828000, has_multimodal=True),
    "gpt-4.1-mini": _create_compatible_model_entry("gpt-4.1-mini", max_token=828000, has_multimodal=True),
    "gpt-4.1-nano": _create_compatible_model_entry("gpt-4.1-nano", max_token=828000, has_multimodal=True),
    
    # o-series models
    "o1-mini": _create_compatible_model_entry(
        "o1-mini", max_token=128000,
        openai_disable_system_prompt=True,
        openai_disable_stream=True,
        openai_force_temperature_one=True
    ),
    "o1-preview": _create_compatible_model_entry(
        "o1-preview", max_token=128000,
        openai_disable_system_prompt=True,
        openai_disable_stream=True,
        openai_force_temperature_one=True
    ),
    "o1": _create_compatible_model_entry(
        "o1", max_token=200000,
        openai_disable_system_prompt=True,
        openai_disable_stream=True,
        openai_force_temperature_one=True
    ),
    "o3-mini": _create_compatible_model_entry(
        "o3-mini", max_token=200000,
        openai_disable_system_prompt=True,
        openai_disable_stream=True,
        openai_force_temperature_one_one=True
    ),
    
    # Anthropic Models
    "claude-3-opus-20240229": _create_compatible_model_entry("claude-3-opus-20240229", max_token=200000),
    "claude-3-opus": _create_compatible_model_entry("claude-3-opus", max_token=200000),
    "claude-3-sonnet-20240229": _create_compatible_model_entry("claude-3-sonnet-20240229", max_token=200000),
    "claude-3-sonnet": _create_compatible_model_entry("claude-3-sonnet", max_token=200000),
    "claude-3-haiku-20240307": _create_compatible_model_entry("claude-3-haiku-20240307", max_token=200000),
    "claude-3-haiku": _create_compatible_model_entry("claude-3-haiku", max_token=200000),
    "claude-3-5-sonnet-20240620": _create_compatible_model_entry("claude-3-5-sonnet-20240620", max_token=200000),
    "claude-3-5-sonnet-20241022": _create_compatible_model_entry("claude-3-5-sonnet-20241022", max_token=200000),
    "claude-3-5-sonnet": _create_compatible_model_entry("claude-3-5-sonnet", max_token=200000),
    
    # Qwen Models
    "qwen-max": _create_compatible_model_entry("qwen-max", max_token=32000),
    "qwen-max-latest": _create_compatible_model_entry("qwen-max-latest", max_token=32000),
    "qwen-max-2025-01-25": _create_compatible_model_entry("qwen-max-2025-01-25", max_token=32000),
    "qwen-plus": _create_compatible_model_entry("qwen-plus", max_token=32000),
    "qwen-turbo": _create_compatible_model_entry("qwen-turbo", max_token=32000),
    "qwen3.5-plus": _create_compatible_model_entry("qwen3.5-plus", max_token=32000),
    
    # Dashscope Models
    "dashscope-qwen3-14b": _create_compatible_model_entry("dashscope-qwen3-14b", max_token=32000),
    "dashscope-qwen3-32b": _create_compatible_model_entry("dashscope-qwen3-32b", max_token=32000),
    "dashscope-qwen3-235b-a22b": _create_compatible_model_entry("dashscope-qwen3-235b-a22b", max_token=32000),
    "dashscope-deepseek-r1": _create_compatible_model_entry("dashscope-deepseek-r1", max_token=64000),
    "dashscope-deepseek-v3": _create_compatible_model_entry("dashscope-deepseek-v3", max_token=64000),
}


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """Get model info for a specific model."""
    return model_info.get(model_name)


def list_models() -> list:
    """List all available models."""
    return list(model_info.keys())


__all__ = [
    "predict",
    "predict_no_ui_long_connection",
    "model_info",
    "get_model_info",
    "list_models",
]