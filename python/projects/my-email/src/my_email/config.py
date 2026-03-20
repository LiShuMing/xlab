from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Gmail
    gmail_credentials_file: Path = Path("credentials/client_secret.json")
    gmail_token_file: Path = Path("credentials/token.json")
    gmail_filter_query: str = (
        "from:(*-dev@lists.apache.org) OR from:(announce@apache.org) OR label:newsletters"
    )
    gmail_max_results: int = 100

    # DB
    db_path: Path = Path("data/my_email.db")

    # LLM — OpenAI-compatible; works with Ollama by changing base_url
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_timeout: int = 120

    # Logging
    log_level: str = "INFO"


settings = Settings()
