"""LLM client wrapper with multi-provider support."""

from dataclasses import dataclass
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class LLMConfig:
    """LLM configuration.

    Attributes:
        api_key: API key for the LLM provider.
        base_url: Base URL for the API endpoint.
        model_name: Model identifier (e.g., 'gpt-4o', 'deepseek-chat').
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in response.
        timeout: Request timeout in seconds.
        max_retries: Maximum retry attempts.
    """

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables.

        Returns:
            LLMConfig instance with values from environment.
        """
        import os

        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("MODEL_NAME", "gpt-4o"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")),
        )


class LLMProvider:
    """Abstract base class for LLM providers."""

    def get_chat_model(self, config: LLMConfig) -> BaseChatModel:
        """Get chat model instance.

        Args:
            config: LLM configuration.

        Returns:
            BaseChatModel instance.
        """
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (OpenAI, DeepSeek, etc.)."""

    def get_chat_model(self, config: LLMConfig) -> BaseChatModel:
        """Create OpenAI-compatible chat model.

        Args:
            config: LLM configuration.

        Returns:
            ChatOpenAI instance.

        Raises:
            ValueError: If API key is not provided.
        """
        if not config.api_key:
            raise ValueError("API key is required")

        return ChatOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )


class LLMClient:
    """LLM client for unified multi-model access.

    This client provides a consistent interface for interacting with
    various LLM providers through a unified API.

    Example:
        >>> client = LLMClient()
        >>> response = client.model.invoke([HumanMessage(content="Hello")])
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM client.

        Args:
            config: Optional LLM configuration. Uses environment if not provided.
        """
        self.config = config or LLMConfig.from_env()
        self._model: Optional[BaseChatModel] = None

    @property
    def model(self) -> BaseChatModel:
        """Lazily load model instance.

        Returns:
            BaseChatModel instance.
        """
        if self._model is None:
            provider = self._get_provider()
            self._model = provider.get_chat_model(self.config)
        return self._model

    def _get_provider(self) -> LLMProvider:
        """Get provider instance based on configuration.

        Returns:
            LLMProvider instance.
        """
        return OpenAIProvider()

    def with_temperature(self, temperature: float) -> "LLMClient":
        """Create new client with specified temperature.

        Args:
            temperature: New temperature value.

        Returns:
            New LLMClient instance.
        """
        new_config = LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        )
        return LLMClient(new_config)

    def with_max_tokens(self, max_tokens: int) -> "LLMClient":
        """Create new client with specified max_tokens.

        Args:
            max_tokens: New max tokens value.

        Returns:
            New LLMClient instance.
        """
        new_config = LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=max_tokens,
        )
        return LLMClient(new_config)


@dataclass
class LLMResponse:
    """LLM response wrapper.

    Attributes:
        content: Response text content.
        model: Model identifier.
        usage: Token usage statistics.
        finish_reason: Reason for generation stopping.
    """

    content: str
    model: str
    usage: dict
    finish_reason: Optional[str] = None

    @classmethod
    def from_langchain(cls, response: any) -> "LLMResponse":
        """Create from LangChain response.

        Args:
            response: LangChain AIMessage response.

        Returns:
            LLMResponse instance.
        """
        usage_metadata = getattr(response, "usage_metadata", {})
        return cls(
            content=str(response.content),
            model=getattr(response, "model", "unknown"),
            usage={
                "prompt_tokens": usage_metadata.get("input_token_count", 0),
                "completion_tokens": usage_metadata.get("output_token_count", 0),
                "total_tokens": usage_metadata.get("total_token_count", 0),
            },
            finish_reason=getattr(response, "response_metadata", {}).get("finish_reason"),
        )


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
