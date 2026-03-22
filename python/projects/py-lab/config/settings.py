"""
Centralized configuration management for the AI Lab Platform.
All API keys, model parameters, and paths are managed here.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from ~/.env first (global config), then local .env
load_dotenv(Path.home() / ".env")
load_dotenv(override=True)

# Base paths
BASE_DIR = Path(__file__).parent.parent
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
VECTOR_STORE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class Settings:
    """Application settings loaded from environment variables."""
    
    # API Keys
    DASHSCOPE_API_KEY: Optional[str] = os.getenv("DASHSCOPE_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Qwen Coding Plan (special API for coding tasks)
    # Get from: https://help.aliyun.com/zh/model-studio/coding-plan-quickstart
    DASHSCOPE_CODING_API_KEY: Optional[str] = os.getenv("DASHSCOPE_CODING_API_KEY")
    DASHSCOPE_CODING_BASE_URL: Optional[str] = os.getenv(
        "DASHSCOPE_CODING_BASE_URL", 
        "https://coding.dashscope.aliyuncs.com/v1"
    )
    
    # Optional: Custom base URL for Anthropic (for proxy/enterprise endpoints)
    ANTHROPIC_BASE_URL: Optional[str] = os.getenv("ANTHROPIC_BASE_URL")
    
    # LLM Configuration
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "qwen")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen-turbo")
    
    # Model Parameters
    DEFAULT_TEMPERATURE: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
    DEFAULT_MAX_TOKENS: int = int(os.getenv("DEFAULT_MAX_TOKENS", "2000"))
    
    # Qwen Models
    QWEN_MODELS = {
        "qwen-turbo": "qwen-turbo",
        "qwen-plus": "qwen-plus",
        "qwen-max": "qwen-max",
        "qwen-max-longcontext": "qwen-max-longcontext",
    }
    
    # Qwen Coding Models (requires Coding Plan subscription)
    # Model list: https://help.aliyun.com/zh/model-studio/models
    QWEN_CODING_MODELS = {
        "qwen3.5-plus": "qwen3.5-plus",           # General purpose, supports images
        "qwen3-coder-plus": "qwen3-coder-plus",   # Optimized for coding
        "qwen3-coder-next": "qwen3-coder-next",   # Latest coder model
        "qwen3-max-2026-01-23": "qwen3-max-2026-01-23",  # Max model with thinking
    }
    
    # OpenAI Models
    OPENAI_MODELS = {
        "gpt-3.5-turbo": "gpt-3.5-turbo",
        "gpt-4": "gpt-4",
        "gpt-4-turbo": "gpt-4-turbo-preview",
    }
    
    # Embedding Configuration
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "dashscope")
    DASHSCOPE_EMBEDDING_MODEL: str = os.getenv(
        "DASHSCOPE_EMBEDDING_MODEL", 
        "text-embedding-v2"
    )
    
    # RAG Configuration
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "4"))
    
    # Vector Store
    FAISS_INDEX_PATH: Path = VECTOR_STORE_DIR / "faiss_index"
    
    @classmethod
    def validate_api_key(cls, provider: str) -> bool:
        """Check if API key is configured for the given provider."""
        if provider == "qwen":
            return bool(cls.DASHSCOPE_API_KEY)
        elif provider == "qwen-coder":
            return bool(cls.DASHSCOPE_CODING_API_KEY)
        elif provider == "openai":
            return bool(cls.OPENAI_API_KEY)
        elif provider == "anthropic":
            return bool(cls.ANTHROPIC_API_KEY)
        return False
    
    @classmethod
    def get_available_models(cls, provider: str) -> dict:
        """Get available models for the given provider."""
        if provider == "qwen":
            return cls.QWEN_MODELS
        elif provider == "qwen-coder":
            return cls.QWEN_CODING_MODELS
        elif provider == "openai":
            return cls.OPENAI_MODELS
        return {}


# Global settings instance
settings = Settings()
