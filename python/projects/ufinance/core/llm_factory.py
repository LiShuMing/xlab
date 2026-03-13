"""
LLM Factory module for unified model access.
Supports Qwen, OpenAI, and Anthropic providers with seamless switching.
"""

from typing import Optional, Union
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_community.chat_models import ChatTongyi
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import streamlit as st

from config.settings import settings


def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    streaming: bool = True,
    **kwargs
) -> BaseChatModel:
    """
    Factory function to get LLM instance based on provider.
    
    Args:
        provider: LLM provider ("qwen", "openai", "anthropic"). 
                  Defaults to settings.DEFAULT_PROVIDER.
        model_name: Specific model name. Defaults to provider's default.
        temperature: Sampling temperature (0-2). Defaults to settings.DEFAULT_TEMPERATURE.
        max_tokens: Maximum tokens to generate. Defaults to settings.DEFAULT_MAX_TOKENS.
        streaming: Enable streaming output. Defaults to True.
        **kwargs: Additional provider-specific parameters.
    
    Returns:
        BaseChatModel: Configured LLM instance.
    
    Raises:
        ValueError: If provider is not supported or API key is missing.
    """
    provider = provider or settings.DEFAULT_PROVIDER
    temperature = temperature if temperature is not None else settings.DEFAULT_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else settings.DEFAULT_MAX_TOKENS
    
    if not settings.validate_api_key(provider):
        raise ValueError(
            f"API key for provider '{provider}' is not configured. "
            f"Please set the corresponding environment variable."
        )
    
    if provider == "qwen":
        model = model_name or settings.DEFAULT_MODEL
        return ChatTongyi(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            dashscope_api_key=settings.DASHSCOPE_API_KEY,
            **kwargs
        )
    
    elif provider == "qwen-coder":
        # Qwen Coding Plan uses OpenAI-compatible API
        model = model_name or "qwen3-coder-plus"
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            api_key=settings.DASHSCOPE_CODING_API_KEY,
            base_url=settings.DASHSCOPE_CODING_BASE_URL,
            **kwargs
        )
    
    elif provider == "openai":
        model = model_name or "gpt-3.5-turbo"
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            api_key=settings.OPENAI_API_KEY,
            **kwargs
        )
    
    elif provider == "anthropic":
        model = model_name or "claude-3-sonnet-20240229"
        anthropic_kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "streaming": streaming,
            "api_key": settings.ANTHROPIC_API_KEY,
        }
        # Add base_url if configured
        if settings.ANTHROPIC_BASE_URL:
            anthropic_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        anthropic_kwargs.update(kwargs)
        return ChatAnthropic(**anthropic_kwargs)
    
    else:
        raise ValueError(
            f"Unsupported provider: {provider}. "
            f"Supported providers: qwen, openai, anthropic"
        )


@st.cache_resource
def get_cached_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    _cache_key: Optional[str] = None
) -> BaseChatModel:
    """
    Cached version of get_llm to avoid recreating model instances.
    Use _cache_key to force refresh when needed.
    
    Args:
        provider: LLM provider.
        model_name: Specific model name.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens.
        _cache_key: Optional cache invalidation key.
    
    Returns:
        BaseChatModel: Cached LLM instance.
    """
    return get_llm(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True
    )


def get_available_providers() -> list[str]:
    """Get list of configured providers."""
    providers = []
    if settings.DASHSCOPE_API_KEY:
        providers.append("qwen")
    if settings.DASHSCOPE_CODING_API_KEY:
        providers.append("qwen-coder")
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    return providers


def get_embedding_model():
    """
    Get embedding model based on configuration.
    
    Returns:
        Embeddings instance for vector operations.
    """
    from langchain_community.embeddings import DashScopeEmbeddings
    
    if settings.EMBEDDING_PROVIDER == "dashscope":
        return DashScopeEmbeddings(
            model=settings.DASHSCOPE_EMBEDDING_MODEL,
            dashscope_api_key=settings.DASHSCOPE_API_KEY
        )
    
    raise ValueError(f"Unsupported embedding provider: {settings.EMBEDDING_PROVIDER}")
