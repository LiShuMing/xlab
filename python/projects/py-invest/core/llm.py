"""LLM client wrapper using OpenAI SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI


@dataclass
class LLMConfig:
    """LLM configuration.

    Attributes:
        api_key: API key for the LLM provider.
        base_url: Base URL for the API endpoint.
        model_name: Model identifier (e.g., 'qwen-plus', 'gpt-4o').
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.
        timeout: Request timeout in seconds.
    """

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model_name: str = "qwen-plus"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 120

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from ~/.env file.

        Returns:
            LLMConfig instance with values from environment.
        """
        env_path = Path.home() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model_name=os.getenv("LLM_MODEL", "qwen-plus"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        )


@lru_cache(maxsize=1)
def _get_cached_config() -> LLMConfig:
    """Get cached LLM config."""
    return LLMConfig.from_env()


class LLMClient:
    """LLM client for OpenAI-compatible APIs.

    This client wraps the OpenAI SDK for use with various LLM providers
    including Qwen (DashScope), Kimi, and standard OpenAI models.

    Example:
        >>> client = LLMClient()
        >>> response = await client.chat("你好")
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM client.

        Args:
            config: Optional LLM configuration. Uses ~/.env if not provided.
        """
        self.config = config or _get_cached_config()
        self._sync_client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def model(self) -> "ModelProperty":
        """Get model property for langchain-like access.

        Returns:
            ModelProperty instance with invoke/ainvoke methods.
        """
        return ModelProperty(self)

    def _get_async_client(self) -> AsyncOpenAI:
        """Get async OpenAI client.

        Returns:
            AsyncOpenAI instance.
        """
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._async_client

    def _get_sync_client(self) -> OpenAI:
        """Get sync OpenAI client.

        Returns:
            OpenAI instance.
        """
        if self._sync_client is None:
            self._sync_client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._sync_client

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """Send chat completion request.

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.
        """
        client = self._get_async_client()
        response = await client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        return response.choices[0].message.content

    def chat_sync(self, messages: list[dict], **kwargs) -> str:
        """Send synchronous chat completion request.

        Args:
            messages: List of message dicts with role/content.
            **kwargs: Additional args for chat.completions.create.

        Returns:
            Response content string.
        """
        client = self._get_sync_client()
        response = client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            **kwargs
        )
        return response.choices[0].message.content

    def with_temperature(self, temperature: float) -> "LLMClient":
        """Create new client with specified temperature.

        Args:
            temperature: New temperature value.

        Returns:
            New LLMClient instance.
        """
        return LLMClient(LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        ))

    def with_max_tokens(self, max_tokens: int) -> "LLMClient":
        """Create new client with specified max_tokens.

        Args:
            max_tokens: New max tokens value.

        Returns:
            New LLMClient instance.
        """
        return LLMClient(LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=max_tokens,
        ))


class ModelProperty:
    """Property wrapper for langchain-like model access."""

    def __init__(self, client: LLMClient):
        self.client = client

    def _convert_messages(self, messages: list) -> list[dict]:
        """Convert langchain messages to OpenAI format.

        Args:
            messages: List of langchain Message objects.

        Returns:
            List of dicts with role/content in OpenAI format.
        """
        role_map = {
            "human": "user",
            "ai": "assistant",
            "assistant": "assistant",
            "system": "system",
            "user": "user",
        }
        result = []
        for m in messages:
            msg_type = getattr(m, "type", "user")
            role = role_map.get(msg_type, "user")
            result.append({"role": role, "content": m.content})
        return result

    def invoke(self, messages: list) -> "AIMessage":
        """Synchronous invoke (langchain compatible).

        Args:
            messages: List of langchain Message objects.

        Returns:
            AIMessage with response content.
        """
        msg_dicts = self._convert_messages(messages)
        content = self.client.chat_sync(msg_dicts)
        return AIMessage(content=content)

    async def ainvoke(self, messages: list) -> "AIMessage":
        """Async invoke (langchain compatible).

        Args:
            messages: List of langchain Message objects.

        Returns:
            AIMessage with response content.
        """
        msg_dicts = self._convert_messages(messages)
        content = await self.client.chat(msg_dicts)
        return AIMessage(content=content)


class AIMessage:
    """Simple AI message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "assistant"

    def __repr__(self) -> str:
        return f"AIMessage(content={self.content!r})"


class HumanMessage:
    """Human message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "human"

    def __repr__(self) -> str:
        return f"HumanMessage(content={self.content!r})"


class SystemMessage:
    """System message wrapper for langchain compatibility."""

    def __init__(self, content: str):
        self.content = content
        self.type = "system"

    def __repr__(self) -> str:
        return f"SystemMessage(content={self.content!r})"


async def create_llm_client(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
) -> LLMClient:
    """Factory function to create LLM client.

    Args:
        model_name: Optional model name override.
        temperature: Optional temperature override.

    Returns:
        Configured LLMClient instance.
    """
    config = LLMConfig.from_env()

    if model_name:
        config.model_name = model_name
    if temperature is not None:
        config.temperature = temperature

    return LLMClient(config)
