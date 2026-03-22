from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_from_env_file(env_path: Path, keys: list[str]) -> dict[str, str]:
    """Load specific keys from an env file."""
    result = {}
    if not env_path.exists():
        return result
    
    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            if key in keys:
                result[key] = value.strip()
    return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gmail
    gmail_credentials_file: Path = Path.home() / ".credentials/my-email/client_secret.json"
    gmail_token_file: Path = Path.home() / ".credentials/my-email/token.json"
    gmail_filter_query: str = (
        "from:(*-dev@lists.apache.org) OR from:(announce@apache.org) OR label:newsletters"
    )
    gmail_max_results: int = 100
    gmail_timeout: int = 60  # HTTP timeout in seconds for Gmail API calls
    gmail_proxy: str = ""  # HTTP proxy for Gmail API (e.g., http://127.0.0.1:7890)

    # DB
    db_path: Path = Path("data/my_email.db")

    # LLM — loaded from ~/.env (global config)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: int = 120

    # Logging
    log_level: str = "INFO"


def _get_settings() -> Settings:
    """Create settings, loading LLM config from ~/.env."""
    settings = Settings()
    
    # Load LLM settings from ~/.env
    global_env = Path.home() / ".env"
    llm_keys = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT", "LOG_LEVEL"]
    global_config = _load_from_env_file(global_env, llm_keys)
    
    # Override with global config if present
    if global_config.get("LLM_BASE_URL"):
        settings.llm_base_url = global_config["LLM_BASE_URL"]
    if global_config.get("LLM_API_KEY"):
        settings.llm_api_key = global_config["LLM_API_KEY"]
    if global_config.get("LLM_MODEL"):
        settings.llm_model = global_config["LLM_MODEL"]
    if global_config.get("LLM_TIMEOUT"):
        settings.llm_timeout = int(global_config["LLM_TIMEOUT"])
    if global_config.get("LOG_LEVEL"):
        settings.log_level = global_config["LOG_LEVEL"]
    
    return settings


settings = _get_settings()
