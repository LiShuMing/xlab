"""
LLM Factory module for unified model access.

Supports Qwen, OpenAI, and Anthropic providers with seamless switching.
Includes tracing and structured logging for observability.
"""

import time
from typing import Any

import streamlit as st
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI

from config.settings import settings
from utils.logger import get_logger, trace_llm_call, trace_llm_io, set_correlation_id

logger = get_logger(__name__)


class TracingCallbackHandler(BaseCallbackHandler):
    """
    Callback handler that traces LLM calls for observability.
    
    Logs input/output payloads and timing information at DEBUG level.
    """
    
    def __init__(self, provider: str, model: str):
        """
        Initialize tracing handler.
        
        Args:
            provider: LLM provider name
            model: Model name
        """
        self.provider = provider
        self.model = model
        self.start_time: float | None = None
        
    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        **kwargs: Any
    ) -> None:
        """Log LLM start with input payload."""
        self.start_time = time.time()
        
        # Trace input
        trace_llm_io(
            logger,
            "input",
            {
                "provider": self.provider,
                "model": self.model,
                "prompt_count": len(prompts),
                "prompts": prompts[:3],  # Limit to first 3 prompts for size
            }
        )
    
    def on_llm_end(self, response: ChatResult, **kwargs: Any) -> None:
        """Log LLM completion with output and timing."""
        latency_ms = (time.time() - self.start_time) * 1000 if self.start_time else None
        
        # Extract token usage if available
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens")
        completion_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens")
        
        # Trace output
        trace_llm_io(
            logger,
            "output",
            {
                "provider": self.provider,
                "model": self.model,
                "generation_count": len(response.generations),
                "token_usage": token_usage,
                "latency_ms": latency_ms,
            }
        )
        
        # Log metrics
        if latency_ms:
            trace_llm_call(
                logger,
                self.provider,
                self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )
    
    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Log LLM errors."""
        latency_ms = (time.time() - self.start_time) * 1000 if self.start_time else None
        
        logger.error(
            "llm_error",
            provider=self.provider,
            model=self.model,
            error_type=type(error).__name__,
            error=str(error),
            latency_ms=latency_ms,
        )


def get_llm(
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    streaming: bool = True,
    enable_tracing: bool | None = None,
    **kwargs: Any
) -> BaseChatModel:
    """
    Factory function to get LLM instance based on provider.
    
    Args:
        provider: LLM provider ("qwen", "qwen-coder", "openai", "anthropic").
                  Defaults to settings.default_provider.
        model_name: Specific model name. Defaults to provider's default.
        temperature: Sampling temperature (0-2). Defaults to settings.default_temperature.
        max_tokens: Maximum tokens to generate. Defaults to settings.default_max_tokens.
        streaming: Enable streaming output. Defaults to True.
        enable_tracing: Enable LLM I/O tracing. Defaults to settings.enable_llm_tracing.
        **kwargs: Additional provider-specific parameters.
    
    Returns:
        Configured LLM instance.
    
    Raises:
        ValueError: If provider is not supported or API key is missing.
    
    Example:
        >>> llm = get_llm(provider="qwen", temperature=0.7)
        >>> response = llm.invoke("Hello, world!")
    """
    provider = provider or settings.default_provider
    temperature = temperature if temperature is not None else settings.default_temperature
    max_tokens = max_tokens if max_tokens is not None else settings.default_max_tokens
    enable_tracing = enable_tracing if enable_tracing is not None else settings.enable_llm_tracing
    
    # Validate API key
    if not settings.validate_api_key(provider):
        error_msg = (
            f"API key for provider '{provider}' is not configured. "
            f"Please set the corresponding environment variable."
        )
        logger.error("missing_api_key", provider=provider)
        raise ValueError(error_msg)
    
    # Build callbacks
    callbacks: list[BaseCallbackHandler] = []
    if enable_tracing:
        callbacks.append(TracingCallbackHandler(provider, model_name or "default"))
    
    logger.debug(
        "creating_llm",
        provider=provider,
        model=model_name,
        temperature=temperature,
        streaming=streaming,
    )
    
    match provider.lower():
        case "qwen":
            model = model_name or settings.default_model
            return ChatTongyi(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
                dashscope_api_key=settings.dashscope_api_key,
                callbacks=callbacks if callbacks else None,
                **kwargs
            )
        
        case "qwen-coder":
            model = model_name or "qwen3-coder-plus"
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
                api_key=settings.dashscope_coding_api_key,
                base_url=settings.dashscope_coding_base_url,
                callbacks=callbacks if callbacks else None,
                **kwargs
            )
        
        case "openai":
            model = model_name or "gpt-3.5-turbo"
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
                api_key=settings.openai_api_key,
                callbacks=callbacks if callbacks else None,
                **kwargs
            )
        
        case "anthropic":
            model = model_name or "claude-3-sonnet-20240229"
            anthropic_kwargs: dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": streaming,
                "api_key": settings.anthropic_api_key,
                "callbacks": callbacks if callbacks else None,
            }
            if settings.anthropic_base_url:
                anthropic_kwargs["base_url"] = settings.anthropic_base_url
            anthropic_kwargs.update(kwargs)
            return ChatAnthropic(**anthropic_kwargs)
        
        case _:
            error_msg = (
                f"Unsupported provider: {provider}. "
                f"Supported providers: qwen, qwen-coder, openai, anthropic"
            )
            logger.error("unsupported_provider", provider=provider)
            raise ValueError(error_msg)


@st.cache_resource
def get_cached_llm(
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    _cache_key: str | None = None
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
        Cached LLM instance.
    
    Note:
        This function uses @st.cache_resource, so the returned instance
        is shared across sessions. Do not modify the instance state.
    """
    return get_llm(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True,
        enable_tracing=False,  # Disable tracing for cached instances
    )


def get_available_providers() -> list[str]:
    """
    Get list of configured providers (those with API keys).
    
    Returns:
        List of provider names that can be used immediately.
    """
    return settings.get_configured_providers()


def get_embedding_model() -> DashScopeEmbeddings:
    """
    Get embedding model based on configuration.
    
    Returns:
        Embeddings instance for vector operations.
    
    Raises:
        ValueError: If the configured embedding provider is not supported.
    """
    match settings.embedding_provider.lower():
        case "dashscope":
            if not settings.dashscope_api_key:
                raise ValueError(
                    "DashScope API key is required for embeddings. "
                    "Please set DASHSCOPE_API_KEY in your .env file."
                )
            return DashScopeEmbeddings(
                model=settings.dashscope_embedding_model,
                dashscope_api_key=settings.dashscope_api_key
            )
        
        case _:
            raise ValueError(
                f"Unsupported embedding provider: {settings.embedding_provider}. "
                f"Supported providers: dashscope"
            )


def count_tokens(messages: list[BaseMessage], model: str = "qwen-turbo") -> int:
    """
    Estimate token count for a list of messages.
    
    Uses a simple heuristic: ~4 characters per token.
    For accurate counts, use tiktoken or provider-specific tokenizers.
    
    Args:
        messages: List of LangChain messages
        model: Model name (for future provider-specific counting)
    
    Returns:
        Estimated token count
    """
    total_chars = sum(len(msg.content) for msg in messages)
    return total_chars // 4
