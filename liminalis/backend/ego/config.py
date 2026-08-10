"""Compatibility adapter for Ego settings.

Ego used to own an independent pydantic-settings tree. The unified runtime now
loads configuration from :mod:`backend.settings`; this module preserves the old
attribute names for Ego callers while keeping a single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from backend.settings import Settings as RuntimeSettings
from backend.settings import get_settings as get_runtime_settings

if TYPE_CHECKING:
    from openai import OpenAI


@dataclass(frozen=True)
class LLMConfig:
    """LLM API configuration."""

    base_url: str
    api_key: str
    model: str
    timeout: int
    max_tokens: int
    max_retries: int


@dataclass(frozen=True)
class EmbeddingConfig:
    """Embedding model configuration."""

    model: str
    use_local: bool


@dataclass(frozen=True)
class ChatConfig:
    """Chat context and memory parameters."""

    history_limit: int
    memory_top_k: int
    max_context_tokens: int


@dataclass(frozen=True)
class AppConfig:
    """Application-wide configuration."""

    log_level: str


@dataclass(frozen=True)
class Settings:
    """Ego-compatible settings view backed by runtime settings."""

    llm: LLMConfig
    embedding: EmbeddingConfig
    chat: ChatConfig
    app: AppConfig

    @classmethod
    def from_runtime(cls, settings: RuntimeSettings) -> Settings:
        return cls(
            llm=LLMConfig(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key or "",
                model=settings.llm_model,
                timeout=int(settings.llm_timeout),
                max_tokens=settings.llm_max_tokens,
                max_retries=settings.llm_max_retries,
            ),
            embedding=EmbeddingConfig(
                model=settings.embedding_model,
                use_local=settings.embedding_use_local,
            ),
            chat=ChatConfig(
                history_limit=settings.ego_chat_history_limit,
                memory_top_k=settings.ego_chat_memory_top_k,
                max_context_tokens=settings.ego_chat_max_context_tokens,
            ),
            app=AppConfig(log_level=settings.log_level.upper()),
        )

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def llm_api_key(self) -> str:
        return self.llm.api_key

    @property
    def llm_timeout(self) -> int:
        return self.llm.timeout

    @property
    def llm_max_tokens(self) -> int:
        return self.llm.max_tokens

    @property
    def llm_max_retries(self) -> int:
        return self.llm.max_retries

    @property
    def embedding_model(self) -> str:
        return self.embedding.model

    @property
    def use_local_embedding(self) -> bool:
        return self.embedding.use_local

    @property
    def chat_history_limit(self) -> int:
        return self.chat.history_limit

    @property
    def chat_memory_top_k(self) -> int:
        return self.chat.memory_top_k

    @property
    def chat_max_context_tokens(self) -> int:
        return self.chat.max_context_tokens

    @property
    def log_level(self) -> str:
        return self.app.log_level


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached Ego-compatible settings."""
    return Settings.from_runtime(get_runtime_settings())


def get_openai_client() -> OpenAI:
    """Get an OpenAI-compatible client instance for embeddings."""
    from openai import OpenAI

    settings = get_settings()
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
