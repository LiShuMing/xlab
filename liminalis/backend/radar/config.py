"""Compatibility adapter for Daily DB Radar settings.

Radar used to keep its own pydantic-settings tree. The unified runtime now
loads environment and env-file values from :mod:`backend.settings`; this module
preserves the old Radar-facing API.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.settings import Settings as RuntimeSettings
from backend.settings import get_settings as get_runtime_settings


@lru_cache
def get_dotenv_values() -> dict:
    """Compatibility hook; root runtime settings now owns env-file loading."""
    return {}


@dataclass(frozen=True)
class Settings:
    """Radar-compatible settings view backed by runtime settings."""

    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout: int
    cache_dir: Path
    output_dir: Path
    feeds_file: Path
    max_items: int
    top_k: int
    days: int
    language: str
    oss_access_key_id: str | None
    oss_access_key_secret: str | None
    oss_endpoint: str
    oss_bucket: str
    oss_prefix: str
    circuit_breaker_failure_threshold: int
    circuit_breaker_recovery_timeout: int
    http_max_connections: int
    http_max_keepalive: int
    http_timeout: int

    @classmethod
    def from_runtime(cls, settings: RuntimeSettings) -> Settings:
        return cls(
            llm_api_key=settings.db_radar_api_key or settings.llm_api_key or "",
            llm_base_url=settings.db_radar_base_url or settings.llm_base_url,
            llm_model=settings.db_radar_model or settings.llm_model,
            llm_timeout=int(settings.db_radar_timeout or settings.llm_timeout),
            cache_dir=settings.radar_cache_dir,
            output_dir=settings.radar_output_dir,
            feeds_file=settings.radar_feeds_file,
            max_items=settings.radar_max_items,
            top_k=settings.radar_top_k,
            days=settings.radar_days,
            language=settings.radar_language,
            oss_access_key_id=settings.radar_oss_access_key_id,
            oss_access_key_secret=settings.radar_oss_access_key_secret,
            oss_endpoint=settings.radar_oss_endpoint,
            oss_bucket=settings.radar_oss_bucket,
            oss_prefix=settings.radar_oss_prefix,
            circuit_breaker_failure_threshold=settings.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=settings.circuit_breaker_recovery_timeout,
            http_max_connections=settings.http_max_connections,
            http_max_keepalive=settings.http_max_keepalive,
            http_timeout=int(settings.http_timeout),
        )

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_api_key(self) -> str:
        """Get the API key as a plain string."""
        return self.llm_api_key

    def get_oss_secret(self) -> str | None:
        """Get the OSS secret as a plain string."""
        return self.oss_access_key_secret


class Config:
    """Backward-compatible configuration holder."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache_dir: Path | None = None,
        output_dir: Path | None = None,
        website_file: Path | None = None,
        feeds_file: Path | None = None,
        max_items: int | None = None,
        top_k: int | None = None,
        days: int | None = None,
        language: str | None = None,
        oss_access_key_id: str | None = None,
        oss_access_key_secret: str | None = None,
        oss_endpoint: str | None = None,
        oss_bucket: str | None = None,
        oss_prefix: str | None = None,
    ):
        """Initialize Config with backward-compatible parameters."""
        settings = get_settings()

        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout
        self.cache_dir = cache_dir or settings.cache_dir
        self.output_dir = output_dir or settings.output_dir
        self.website_file = website_file or Path("websites.txt")
        self.feeds_file = feeds_file or settings.feeds_file
        self.max_items = max_items or settings.max_items
        self.top_k = top_k or settings.top_k
        self.days = days or settings.days
        self.language = language or settings.language

        self.oss_access_key_id = oss_access_key_id or settings.oss_access_key_id
        self.oss_access_key_secret = oss_access_key_secret or settings.get_oss_secret()
        self.oss_endpoint = oss_endpoint or settings.oss_endpoint
        self.oss_bucket = oss_bucket or settings.oss_bucket
        self.oss_prefix = oss_prefix or settings.oss_prefix

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get the cached Radar-compatible settings instance."""
    return Settings.from_runtime(get_runtime_settings())


_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance (backward compatible)."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance (backward compatible)."""
    global _config
    _config = config
