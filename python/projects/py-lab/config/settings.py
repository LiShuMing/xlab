"""
Centralized configuration management for the AI Lab Platform.
All API keys, model parameters, and paths are managed here using Pydantic Settings.
"""

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from ~/.env first (global config), then local .env
load_dotenv(Path.home() / ".env")
load_dotenv(override=True)

# Base paths
BASE_DIR: Path = Path(__file__).parent.parent
VECTOR_STORE_DIR: Path = BASE_DIR / "vector_store"
LOGS_DIR: Path = BASE_DIR / "logs"

# Ensure directories exist
VECTOR_STORE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses Pydantic v2 Settings for validation and type safety.
    All settings can be overridden via environment variables or .env file.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # API Keys
    dashscope_api_key: str | None = Field(
        default=None,
        description="DashScope API key for Qwen models"
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key"
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key"
    )
    
    # Qwen Coding Plan (special API for coding tasks)
    dashscope_coding_api_key: str | None = Field(
        default=None,
        description="DashScope Coding Plan API key"
    )
    dashscope_coding_base_url: str = Field(
        default="https://coding.dashscope.aliyuncs.com/v1",
        description="Base URL for Qwen Coding API"
    )
    
    # Optional: Custom base URL for Anthropic
    anthropic_base_url: str | None = Field(
        default=None,
        description="Custom base URL for Anthropic API (for proxy/enterprise)"
    )
    
    # LLM Configuration
    default_provider: str = Field(
        default="qwen",
        description="Default LLM provider"
    )
    default_model: str = Field(
        default="qwen-turbo",
        description="Default model name"
    )
    
    # Model Parameters
    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature"
    )
    default_max_tokens: int = Field(
        default=2000,
        ge=100,
        le=16000,
        description="Default maximum tokens to generate"
    )
    
    # Embedding Configuration
    embedding_provider: str = Field(
        default="dashscope",
        description="Embedding provider"
    )
    dashscope_embedding_model: str = Field(
        default="text-embedding-v2",
        description="DashScope embedding model"
    )
    
    # RAG Configuration
    chunk_size: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Text chunk size for RAG"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Chunk overlap for RAG"
    )
    top_k_retrieval: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Top-K retrieval for RAG"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    log_to_file: bool = Field(
        default=True,
        description="Whether to log to file"
    )
    
    # Observability
    enable_llm_tracing: bool = Field(
        default=True,
        description="Enable LLM I/O tracing"
    )
    
    @property
    def qwen_models(self) -> dict[str, str]:
        """Get available Qwen models."""
        return {
            "qwen-turbo": "qwen-turbo",
            "qwen-plus": "qwen-plus",
            "qwen-max": "qwen-max",
            "qwen-max-longcontext": "qwen-max-longcontext",
        }
    
    @property
    def qwen_coding_models(self) -> dict[str, str]:
        """Get available Qwen Coding models."""
        return {
            "qwen3.5-plus": "qwen3.5-plus",
            "qwen3-coder-plus": "qwen3-coder-plus",
            "qwen3-coder-next": "qwen3-coder-next",
            "qwen3-max-2026-01-23": "qwen3-max-2026-01-23",
        }
    
    @property
    def openai_models(self) -> dict[str, str]:
        """Get available OpenAI models."""
        return {
            "gpt-3.5-turbo": "gpt-3.5-turbo",
            "gpt-4": "gpt-4",
            "gpt-4-turbo": "gpt-4-turbo-preview",
            "gpt-4o": "gpt-4o",
        }
    
    @property
    def anthropic_models(self) -> dict[str, str]:
        """Get available Anthropic models."""
        return {
            "claude-3-sonnet": "claude-3-sonnet-20240229",
            "claude-3-opus": "claude-3-opus-20240229",
            "claude-3-haiku": "claude-3-haiku-20240307",
        }
    
    @property
    def faiss_index_path(self) -> Path:
        """Get FAISS index path."""
        return VECTOR_STORE_DIR / "faiss_index"
    
    def validate_api_key(self, provider: str) -> bool:
        """
        Check if API key is configured for the given provider.
        
        Args:
            provider: LLM provider identifier
            
        Returns:
            True if API key is configured, False otherwise
        """
        match provider.lower():
            case "qwen":
                return bool(self.dashscope_api_key)
            case "qwen-coder":
                return bool(self.dashscope_coding_api_key)
            case "openai":
                return bool(self.openai_api_key)
            case "anthropic":
                return bool(self.anthropic_api_key)
            case _:
                return False
    
    def get_available_models(self, provider: str) -> dict[str, str]:
        """
        Get available models for the given provider.
        
        Args:
            provider: LLM provider identifier
            
        Returns:
            Dictionary of model names to model IDs
        """
        match provider.lower():
            case "qwen":
                return self.qwen_models
            case "qwen-coder":
                return self.qwen_coding_models
            case "openai":
                return self.openai_models
            case "anthropic":
                return self.anthropic_models
            case _:
                return {}
    
    def get_configured_providers(self) -> list[str]:
        """
        Get list of configured (has API key) providers.
        
        Returns:
            List of provider names with valid API keys
        """
        providers: list[str] = []
        if self.dashscope_api_key:
            providers.append("qwen")
        if self.dashscope_coding_api_key:
            providers.append("qwen-coder")
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        return providers


# Global settings instance
settings = Settings()
