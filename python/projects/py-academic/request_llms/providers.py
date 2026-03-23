"""
Concrete LLM provider implementations.

Implements providers for OpenAI, Anthropic (Claude), and Qwen (Aliyun).
"""

from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

from .core import ChatConfig, ChatResponse, LLMProvider, Message, Role


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider (supports OpenAI and compatible APIs).
    
    Compatible with:
    - OpenAI official API
    - Azure OpenAI
    - Custom OpenAI-compatible endpoints
    
    Example:
        >>> provider = OpenAIProvider(
        ...     model="gpt-4o",
        ...     api_key="sk-...",
        ...     base_url="https://api.openai.com/v1"  # Optional
        ... )
        >>> response = await provider.chat([Message.user("Hello!")])
    """
    
    SUPPORTED_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o4-mini",
    ]
    
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    
    # Context lengths for different models
    CONTEXT_LENGTHS = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4.1": 1047576,
        "gpt-4.1-mini": 1047576,
        "gpt-4.1-nano": 1047576,
        "gpt-4-turbo": 128000,
        "gpt-4": 8192,
        "gpt-3.5-turbo": 16385,
        "o1": 200000,
        "o1-preview": 128000,
        "o1-mini": 128000,
        "o3": 200000,
        "o3-mini": 200000,
        "o4-mini": 200000,
    }
    
    def __init__(
        self, 
        model: str, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            model: Model identifier (e.g., "gpt-4o")
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: API base URL for custom endpoints
        """
        super().__init__(model, api_key, **kwargs)
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. "
                "Set OPENAI_API_KEY environment variable or pass api_key."
            )
        
        self.base_url = base_url or self.config.get("base_url") or self.DEFAULT_BASE_URL
        self.base_url = self.base_url.rstrip("/")
        
        # Initialize HTTP client
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    
    async def chat(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> ChatResponse:
        """Send chat completion request to OpenAI."""
        config = config or ChatConfig()
        
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "stream": False,
            **config.extra,
        }
        
        if config.max_tokens:
            payload["max_tokens"] = config.max_tokens
        
        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            choice = data["choices"][0]
            message = Message.assistant(
                content=choice["message"]["content"],
            )
            
            return ChatResponse(
                message=message,
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
                raw_response=data,
            )
            
        except httpx.HTTPError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def chat_stream(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from OpenAI."""
        config = config or ChatConfig()
        
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "stream": True,
            **config.extra,
        }
        
        if config.max_tokens:
            payload["max_tokens"] = config.max_tokens
        
        try:
            async with self._client.stream(
                "POST", "/chat/completions", 
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        try:
                            import json
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue
                            
        except httpx.HTTPError as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (approximation)."""
        try:
            import tiktoken
            encoder = tiktoken.encoding_for_model(self.model)
            return len(encoder.encode(text))
        except Exception:
            # Fallback: rough approximation (4 chars per token)
            return len(text) // 4
    
    @property
    def max_context_length(self) -> int:
        """Get max context length for the model."""
        return self.CONTEXT_LENGTHS.get(self.model, 4096)


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider.
    
    Supports Claude 3, Claude 3.5, Claude 3.7 and Claude 4 models.
    Also supports Claude-compatible endpoints (e.g., via DashScope).
    
    Example:
        >>> provider = AnthropicProvider(
        ...     model="claude-sonnet-4-5",
        ...     api_key="sk-ant-..."
        ... )
        >>> response = await provider.chat([Message.user("Hello!")])
    """
    
    SUPPORTED_MODELS = [
        "claude-sonnet-4-5",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    
    # Context lengths for Claude models
    CONTEXT_LENGTHS = {
        "claude-sonnet-4-5": 200000,
        "claude-3-7-sonnet-20250219": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-sonnet-20240620": 200000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
    }
    
    def __init__(
        self, 
        model: str, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Anthropic provider.
        
        Args:
            model: Claude model identifier
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Custom base URL for compatible endpoints
        """
        super().__init__(model, api_key, **kwargs)
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. "
                "Set ANTHROPIC_API_KEY environment variable or pass api_key."
            )
        
        self.base_url = base_url or self.config.get("base_url") or self.DEFAULT_BASE_URL
        self.base_url = self.base_url.rstrip("/")
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    
    async def chat(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> ChatResponse:
        """Send chat completion request to Anthropic."""
        config = config or ChatConfig()
        
        # Separate system message from conversation
        system_message = ""
        conversation = []
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_message = msg.content
            else:
                conversation.append({
                    "role": "assistant" if msg.role == Role.ASSISTANT else "user",
                    "content": msg.content,
                })
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": config.max_tokens or 4096,
            **config.extra,
        }
        
        if system_message:
            payload["system"] = system_message
        
        if config.temperature != 1.0:
            payload["temperature"] = config.temperature
        
        if config.top_p != 1.0:
            payload["top_p"] = config.top_p
        
        try:
            response = await self._client.post("/messages", json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            
            message = Message.assistant(content=content)
            
            return ChatResponse(
                message=message,
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                finish_reason=data.get("stop_reason"),
                raw_response=data,
            )
            
        except httpx.HTTPError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    async def chat_stream(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Anthropic."""
        config = config or ChatConfig()
        
        system_message = ""
        conversation = []
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_message = msg.content
            else:
                conversation.append({
                    "role": "assistant" if msg.role == Role.ASSISTANT else "user",
                    "content": msg.content,
                })
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": conversation,
            "max_tokens": config.max_tokens or 4096,
            "stream": True,
            **config.extra,
        }
        
        if system_message:
            payload["system"] = system_message
        
        if config.temperature != 1.0:
            payload["temperature"] = config.temperature
        
        try:
            async with self._client.stream(
                "POST", "/messages", 
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    
                    try:
                        import json
                        event = json.loads(data)
                        
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue
                        
        except httpx.HTTPError as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count tokens (approximation for Claude)."""
        # Claude uses roughly similar tokenization to GPT
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except Exception:
            return len(text) // 4
    
    @property
    def max_context_length(self) -> int:
        """Get max context length for the model."""
        return self.CONTEXT_LENGTHS.get(self.model, 200000)


class QwenProvider(LLMProvider):
    """
    Alibaba Qwen (DashScope) API provider.
    
    Supports Qwen series models including:
    - qwen-max, qwen-plus, qwen-turbo
    - qwen3.5-plus
    - dashscope-qwen3-* models
    - dashscope-deepseek models (via DashScope)
    
    Also supports custom Qwen-compatible endpoints via QWEN_BASE_URL.
    
    Example:
        >>> provider = QwenProvider(
        ...     model="qwen3.5-plus",
        ...     api_key="sk-..."  # or set QWEN_API_KEY env var
        ... )
        >>> response = await provider.chat([Message.user("Hello!")])
    """
    
    SUPPORTED_MODELS = [
        "qwen-max",
        "qwen-max-latest",
        "qwen-max-2025-01-25",
        "qwen-plus",
        "qwen-turbo",
        "qwen3.5-plus",
        "dashscope-qwen3-14b",
        "dashscope-qwen3-32b",
        "dashscope-qwen3-235b-a22b",
        "dashscope-deepseek-r1",
        "dashscope-deepseek-v3",
    ]
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
    
    # Context lengths for Qwen models
    CONTEXT_LENGTHS = {
        "qwen-max": 32768,
        "qwen-max-latest": 32768,
        "qwen-max-2025-01-25": 32768,
        "qwen-plus": 131072,
        "qwen-turbo": 131072,
        "qwen3.5-plus": 131072,
        "dashscope-qwen3-14b": 131072,
        "dashscope-qwen3-32b": 131072,
        "dashscope-qwen3-235b-a22b": 131072,
        "dashscope-deepseek-r1": 65536,
        "dashscope-deepseek-v3": 65536,
    }
    
    def __init__(
        self, 
        model: str, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Qwen provider.
        
        Args:
            model: Qwen model identifier
            api_key: API key (defaults to QWEN_API_KEY or DASHSCOPE_API_KEY env var)
            base_url: Custom base URL for compatible endpoints
        """
        super().__init__(model, api_key, **kwargs)
        
        # Priority: passed arg > QWEN_API_KEY > DASHSCOPE_API_KEY
        self.api_key = (
            api_key 
            or os.getenv("QWEN_API_KEY") 
            or os.getenv("DASHSCOPE_API_KEY")
        )
        
        if not self.api_key:
            raise ValueError(
                "Qwen API key required. "
                "Set QWEN_API_KEY or DASHSCOPE_API_KEY environment variable, "
                "or pass api_key."
            )
        
        # Priority: passed arg > QWEN_BASE_URL > default
        self.base_url = (
            base_url 
            or os.getenv("QWEN_BASE_URL")
            or self.DEFAULT_BASE_URL
        )
        self.base_url = self.base_url.rstrip("/")
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    
    def _normalize_model_name(self, model: str) -> str:
        """Remove 'dashscope-' prefix if present."""
        prefix = "dashscope-"
        if model.startswith(prefix):
            return model[len(prefix):]
        return model
    
    async def chat(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> ChatResponse:
        """Send chat completion request to Qwen/DashScope."""
        config = config or ChatConfig()
        
        # Convert messages format
        qwen_messages = []
        system_content = None
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_content = msg.content
            else:
                qwen_messages.append({
                    "role": "assistant" if msg.role == Role.ASSISTANT else "user",
                    "content": msg.content,
                })
        
        # If first message is system, prepend to messages
        if system_content and qwen_messages:
            qwen_messages.insert(0, {
                "role": "system",
                "content": system_content,
            })
        
        payload = {
            "model": self._normalize_model_name(self.model),
            "input": {
                "messages": qwen_messages,
            },
            "parameters": {
                "result_format": "message",
                **config.extra,
            },
        }
        
        if config.temperature != 0.7:
            payload["parameters"]["temperature"] = config.temperature
        
        if config.top_p != 1.0:
            payload["parameters"]["top_p"] = config.top_p
        
        if config.max_tokens:
            payload["parameters"]["max_tokens"] = config.max_tokens
        
        try:
            response = await self._client.post("/services/aigc/text-generation/generation", json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code"):
                raise RuntimeError(f"Qwen API error: {data.get('message', 'Unknown error')}")
            
            output = data.get("output", {})
            choice = output.get("choices", [{}])[0]
            message_data = choice.get("message", {})
            
            content = message_data.get("content", "")
            reasoning = message_data.get("reasoning_content", "")
            
            message = Message.assistant(
                content=content,
                reasoning=reasoning,
            )
            
            return ChatResponse(
                message=message,
                model=self.model,
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
                raw_response=data,
            )
            
        except httpx.HTTPError as e:
            logger.error(f"Qwen API error: {e}")
            raise
    
    async def chat_stream(
        self, 
        messages: List[Message], 
        config: Optional[ChatConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Qwen (using SSE format)."""
        config = config or ChatConfig()
        
        qwen_messages = []
        system_content = None
        
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_content = msg.content
            else:
                qwen_messages.append({
                    "role": "assistant" if msg.role == Role.ASSISTANT else "user",
                    "content": msg.content,
                })
        
        if system_content and qwen_messages:
            qwen_messages.insert(0, {
                "role": "system",
                "content": system_content,
            })
        
        payload = {
            "model": self._normalize_model_name(self.model),
            "input": {
                "messages": qwen_messages,
            },
            "parameters": {
                "result_format": "message",
                "incremental_output": True,
            },
        }
        
        if config.temperature != 0.7:
            payload["parameters"]["temperature"] = config.temperature
        
        try:
            async with self._client.stream(
                "POST",
                "/services/aigc/text-generation/generation",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        import json
                        data = json.loads(line)
                        
                        if data.get("code"):
                            logger.error(f"Qwen streaming error: {data}")
                            continue
                        
                        output = data.get("output", {})
                        choices = output.get("choices", [])
                        if choices:
                            message = choices[0].get("message", {})
                            content = message.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
                        
        except httpx.HTTPError as e:
            logger.error(f"Qwen streaming error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count tokens (approximation for Qwen)."""
        # Qwen uses similar tokenization to GPT
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except Exception:
            return len(text) // 4
    
    @property
    def max_context_length(self) -> int:
        """Get max context length for the model."""
        return self.CONTEXT_LENGTHS.get(self.model, 8192)
