"""
Core abstractions for the LLM provider system.

Defines the protocol/interface that all LLM providers must implement,
along with common data structures and the factory pattern.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Protocol,
    Type,
    Union,
)

from loguru import logger


class Role(str, Enum):
    """Message roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """
    A single message in a conversation.
    
    Attributes:
        role: The message role (system/user/assistant)
        content: The message content
        metadata: Optional metadata (e.g., reasoning content, tokens used)
    """
    role: Role
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def system(cls, content: str) -> Message:
        """Create a system message."""
        return cls(role=Role.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> Message:
        """Create a user message."""
        return cls(role=Role.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str, **metadata) -> Message:
        """Create an assistant message."""
        return cls(role=Role.ASSISTANT, content=content, metadata=metadata)
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to provider-agnostic dictionary format."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class ChatConfig:
    """
    Configuration for chat completions.
    
    Attributes:
        temperature: Sampling temperature (0.0 - 2.0)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        stream: Whether to stream the response
        timeout: Request timeout in seconds
        extra: Provider-specific extra parameters
    """
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: Optional[int] = None
    stream: bool = True
    timeout: float = 60.0
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be in [0.0, 2.0], got {self.temperature}")
        if not 0.0 < self.top_p <= 1.0:
            raise ValueError(f"top_p must be in (0.0, 1.0], got {self.top_p}")


@dataclass
class ChatResponse:
    """
    Response from an LLM chat completion.
    
    Attributes:
        message: The assistant's response message
        model: The model used for generation
        usage: Token usage statistics
        finish_reason: Why the generation stopped
        raw_response: Original provider response (for debugging)
    """
    message: Message
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    raw_response: Optional[Any] = None


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    All new providers must inherit from this class and implement
    the abstract methods. The factory pattern is used for registration.
    """
    
    # Registry of provider implementations
    _registry: ClassVar[Dict[str, Type[LLMProvider]]] = {}
    
    # Supported models by this provider
    SUPPORTED_MODELS: ClassVar[List[str]] = []
    
    def __init_subclass__(cls, **kwargs):
        """Auto-register subclasses in the provider registry."""
        super().__init_subclass__(**kwargs)
        provider_name = cls.__name__.replace("Provider", "").lower()
        LLMProvider._registry[provider_name] = cls
        logger.debug(f"Registered LLM provider: {provider_name}")
    
    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the provider.
        
        Args:
            model: The model identifier
            api_key: API key for authentication
            **kwargs: Provider-specific configuration
        """
        self.model = model
        self.api_key = api_key
        self.config = kwargs
        self._validate_model()
    
    def _validate_model(self) -> None:
        """Validate that the model is supported by this provider."""
        if self.SUPPORTED_MODELS and self.model not in self.SUPPORTED_MODELS:
            supported = ", ".join(self.SUPPORTED_MODELS)
            raise ValueError(
                f"Model '{self.model}' not supported. "
                f"Supported models: {supported}"
            )
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> ChatResponse:
        """
        Send a chat completion request.
        
        Args:
            messages: List of conversation messages
            config: Chat configuration
            
        Returns:
            The LLM response
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion responses.
        
        Args:
            messages: List of conversation messages
            config: Chat configuration
            
        Yields:
            Chunks of the generated text
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in the given text."""
        pass
    
    @property
    @abstractmethod
    def max_context_length(self) -> int:
        """Maximum context length for this model."""
        pass


class LLMFactory:
    """
    Factory for creating LLM provider instances.
    
    Automatically selects the appropriate provider based on model name.
    """
    
    # Model to provider mapping
    MODEL_PROVIDERS: ClassVar[Dict[str, str]] = {}
    
    @classmethod
    def register_model(cls, model: str, provider: str) -> None:
        """Register a model to be handled by a specific provider."""
        cls.MODEL_PROVIDERS[model] = provider.lower()
        logger.debug(f"Registered model '{model}' -> {provider}")
    
    @classmethod
    def create(
        cls, 
        model: str, 
        api_key: Optional[str] = None,
        **kwargs
    ) -> LLMProvider:
        """
        Create an LLM provider instance for the given model.
        
        Args:
            model: The model identifier (e.g., "gpt-4o", "claude-3-opus")
            api_key: API key (optional, can use env var)
            **kwargs: Provider-specific configuration
            
        Returns:
            Configured LLM provider instance
            
        Raises:
            ValueError: If no provider is found for the model
        """
        provider_name = cls.MODEL_PROVIDERS.get(model)
        
        if not provider_name:
            # Try to infer from model name
            if "claude" in model.lower():
                provider_name = "anthropic"
            elif "gpt" in model.lower() or model.startswith("o1") or model.startswith("o3"):
                provider_name = "openai"
            elif "qwen" in model.lower():
                provider_name = "qwen"
            else:
                raise ValueError(f"No provider found for model: {model}")
        
        provider_class = LLMProvider._registry.get(provider_name)
        if not provider_class:
            raise ValueError(f"Provider '{provider_name}' not registered")
        
        return provider_class(model=model, api_key=api_key, **kwargs)
    
    @classmethod
    def list_supported_models(cls) -> List[str]:
        """Get list of all registered models."""
        return list(cls.MODEL_PROVIDERS.keys())
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """Get list of all registered providers."""
        return list(LLMProvider._registry.keys())
