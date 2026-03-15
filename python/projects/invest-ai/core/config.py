"""配置管理 - 基于 pydantic-settings"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "Invest-AI"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "info"

    # LLM 配置
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    model_name: str = "gpt-4o"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4000

    # 数据库配置
    database_url: str = "postgresql://localhost:5432/invest_ai"
    redis_url: str = "redis://localhost:6379/0"

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def llm_config(self) -> dict:
        """获取 LLM 配置字典"""
        return {
            "api_key": self.openai_api_key,
            "base_url": self.openai_base_url,
            "model_name": self.model_name,
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
        }


@lru_cache
def get_settings() -> Settings:
    """获取单例配置实例"""
    return Settings()
