"""Configuration management for Daily DB Radar."""

import os
from pathlib import Path
from typing import Optional


# Load ~/.env file if it exists
def _load_env_file():
    """Load environment variables from ~/.env file."""
    env_path = Path.home() / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Only set if not already set in environment
                    if key not in os.environ:
                        os.environ[key] = value


# Load env file on module import
_load_env_file()


class Config:
    """Configuration holder for the application."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        website_file: Optional[Path] = None,
        feeds_file: Optional[Path] = None,
        max_items: int = 80,
        top_k: int = 10,
        days: int = 7,
        language: str = "en",
        # OSS sync configuration
        oss_access_key_id: Optional[str] = None,
        oss_access_key_secret: Optional[str] = None,
        oss_endpoint: Optional[str] = None,
        oss_bucket: Optional[str] = None,
        oss_prefix: Optional[str] = None,
    ):
        # LLM configuration from ~/.env or environment variables
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", None)
        self.model = model or os.environ.get("LLM_MODEL", "qwen3.5-plus")
        self.timeout = int(os.environ.get("LLM_TIMEOUT", "300"))
        self.cache_dir = cache_dir or Path("cache")
        self.output_dir = output_dir or Path("out")
        # Support both old website_file and new feeds_file
        # Default to feeds.json if it exists, otherwise fall back to websites.txt
        self.website_file = website_file or Path("websites.txt")
        self.feeds_file = feeds_file or Path("feeds.json")
        self.max_items = max_items
        self.top_k = top_k
        self.days = days
        self.language = language  # "en" or "zh"

        # OSS sync configuration from environment variables
        self.oss_access_key_id = oss_access_key_id or os.environ.get("DB_RADAR_OSS_ACCESS_KEY_ID")
        self.oss_access_key_secret = oss_access_key_secret or os.environ.get("DB_RADAR_OSS_ACCESS_KEY_SECRET")
        self.oss_endpoint = oss_endpoint or os.environ.get("DB_RADAR_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
        self.oss_bucket = oss_bucket or os.environ.get("DB_RADAR_OSS_BUCKET", "dbradar-sync")
        self.oss_prefix = oss_prefix or os.environ.get("DB_RADAR_OSS_PREFIX", "sync/")

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
