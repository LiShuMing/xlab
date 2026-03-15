"""LLM 客户端封装 - 支持多模型提供商"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import os

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class LLMConfig:
    """LLM 配置"""

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置"""
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model_name=os.getenv("MODEL_NAME", "gpt-4o"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")),
        )


class LLMProvider(ABC):
    """LLM 提供商接口"""

    @abstractmethod
    def get_chat_model(self, config: LLMConfig) -> BaseChatModel:
        """获取聊天模型"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI 兼容提供商（包括 OpenAI、DeepSeek 等）"""

    def get_chat_model(self, config: LLMConfig) -> BaseChatModel:
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
    """LLM 客户端 - 统一管理多模型"""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig.from_env()
        self._model: Optional[BaseChatModel] = None

    @property
    def model(self) -> BaseChatModel:
        """懒加载模型实例"""
        if self._model is None:
            provider = self._get_provider()
            self._model = provider.get_chat_model(self.config)
        return self._model

    def _get_provider(self) -> LLMProvider:
        """根据配置获取提供商"""
        # 当前只支持 OpenAI 兼容接口
        # 未来可扩展 Qwen、Gemini 等
        return OpenAIProvider()

    def with_temperature(self, temperature: float) -> "LLMClient":
        """返回一个新客户端，使用指定 temperature"""
        new_config = LLMConfig(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model_name=self.config.model_name,
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        )
        return LLMClient(new_config)

    def with_max_tokens(self, max_tokens: int) -> "LLMClient":
        """返回一个新客户端，使用指定 max_tokens"""
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
    """LLM 响应"""

    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: Optional[str] = None

    @classmethod
    def from_langchain(cls, response: Any) -> "LLMResponse":
        """从 LangChain 响应创建"""
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
    """创建 LLM 客户端的工厂函数"""
    config = LLMConfig.from_env()

    if model_name:
        config.model_name = model_name
    if temperature is not None:
        config.temperature = temperature

    return LLMClient(config)
