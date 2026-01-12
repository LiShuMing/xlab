"""Configuration management for Daily DB Radar."""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration holder for the application."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        website_file: Optional[Path] = None,
        max_items: int = 80,
        top_k: int = 10,
        days: int = 7,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", None)
        self.cache_dir = cache_dir or Path("cache")
        self.output_dir = output_dir or Path("out")
        self.website_file = website_file or Path("websites.txt")
        self.max_items = max_items
        self.top_k = top_k
        self.days = days

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
