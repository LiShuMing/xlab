"""Application settings and configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _load_env_file() -> None:
    """Load ~/.env if it exists, without overwriting already-set env vars."""
    env_path = Path.home() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        # Manual fallback: parse key=value lines
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


class Settings(BaseModel):
    """Central settings object. LLM config loaded from ~/.env."""

    data_dir: Path = Path("data")
    products_dir: Path = Path("products")
    db_path: Path = Path("data/app.db")
    raw_dir: Path = Path("data/raw")
    normalized_dir: Path = Path("data/normalized")
    reports_dir: Path = Path("data/reports")

    # GitHub API token (optional, raises rate limit from 60→5000 req/hr)
    github_token: str = ""

    # LLM backend — OpenAI-compatible
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_timeout: int = 120

    def model_post_init(self, __context: object) -> None:
        """Apply environment variable overrides after initialization."""
        _load_env_file()

        self.github_token = os.environ.get("GITHUB_TOKEN", self.github_token)
        self.llm_base_url = os.environ.get("LLM_BASE_URL", self.llm_base_url)
        self.llm_api_key = os.environ.get("LLM_API_KEY", self.llm_api_key)
        self.llm_model = os.environ.get("LLM_MODEL", self.llm_model)
        try:
            self.llm_timeout = int(os.environ.get("LLM_TIMEOUT", str(self.llm_timeout)))
        except ValueError:
            pass

        if data_dir_env := os.environ.get("PIA_DATA_DIR"):
            self.data_dir = Path(data_dir_env)
            self.db_path = self.data_dir / "app.db"
            self.raw_dir = self.data_dir / "raw"
            self.normalized_dir = self.data_dir / "normalized"
            self.reports_dir = self.data_dir / "reports"

        if products_dir_env := os.environ.get("PIA_PRODUCTS_DIR"):
            self.products_dir = Path(products_dir_env)

    def ensure_dirs(self) -> None:
        """Create all necessary directories if they do not exist."""
        for d in [self.data_dir, self.raw_dir, self.normalized_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # Backward-compat alias used in a few places
    @property
    def default_model(self) -> str:
        return self.llm_model


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance, creating it on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
