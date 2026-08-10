"""Configuration management for Daily Stock Analysis Email System.

Loads configuration from ~/.py-invest/config.yaml with environment variable
override for sensitive values like GMAIL_APP_PASSWORD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.settings import Settings as RuntimeSettings
from backend.settings import get_settings as get_runtime_settings

# Configuration file path
CONFIG_PATH = Path.home() / ".py-invest" / "config.yaml"


class ConfigError(Exception):
    """Configuration error."""

    pass


@dataclass
class StockConfig:
    """Stock configuration.

    Attributes:
        code: Stock code (e.g., 'sh600519' for A-shares).
        name: Stock name for display (e.g., 'Guizhou Moutai').
    """

    code: str
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StockConfig:
        """Create StockConfig from dictionary.

        Args:
            data: Dictionary with 'code' and optional 'name' keys.

        Returns:
            StockConfig instance.
        """
        return cls(
            code=data.get("code", ""),
            name=data.get("name", ""),
        )


@dataclass
class EmailConfig:
    """Email configuration for SMTP sending.

    Attributes:
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        sender: Sender email address.
        recipient: Recipient email address.
        password: SMTP authentication password (from env var).
    """

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender: str = ""
    recipient: str = ""
    password: str = ""  # Loaded from GMAIL_APP_PASSWORD env var

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        runtime_settings: RuntimeSettings | None = None,
    ) -> EmailConfig:
        """Create EmailConfig from dictionary.

        Overrides password with unified runtime settings if set.

        Args:
            data: Dictionary with email configuration.
            runtime_settings: Optional unified Liminalis runtime settings.

        Returns:
            EmailConfig instance.
        """
        runtime_settings = runtime_settings or get_runtime_settings()

        return cls(
            smtp_host=data.get("smtp_host", "smtp.gmail.com"),
            smtp_port=data.get("smtp_port", 587),
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            # Security: secrets come from the unified runtime settings layer.
            password=runtime_settings.gmail_app_password or data.get("password", ""),
        )


@dataclass
class AnalysisConfig:
    """Analysis schedule configuration.

    Attributes:
        start_time: Daily analysis start time (HH:MM format).
        timezone: Timezone for scheduling (e.g., 'Asia/Shanghai').
    """

    start_time: str = "07:30"
    timezone: str = "Asia/Shanghai"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisConfig:
        """Create AnalysisConfig from dictionary.

        Args:
            data: Dictionary with analysis configuration.

        Returns:
            AnalysisConfig instance.
        """
        return cls(
            start_time=data.get("start_time", "07:30"),
            timezone=data.get("timezone", "Asia/Shanghai"),
        )


@dataclass
class AppConfig:
    """Application configuration.

    Aggregates all configuration sections.

    Attributes:
        stocks: List of stock configurations.
        email: Email configuration.
        analysis: Analysis schedule configuration.
    """

    stocks: list[StockConfig] = field(default_factory=list)
    email: EmailConfig = field(default_factory=EmailConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        runtime_settings: RuntimeSettings | None = None,
    ) -> AppConfig:
        """Create AppConfig from dictionary.

        Args:
            data: Dictionary with full configuration.
            runtime_settings: Optional unified Liminalis runtime settings.

        Returns:
            AppConfig instance.
        """
        runtime_settings = runtime_settings or get_runtime_settings()
        stocks_data = data.get("stocks", [])
        stocks = [StockConfig.from_dict(s) for s in stocks_data]

        email_data = data.get("email", {})
        email = EmailConfig.from_dict(email_data, runtime_settings=runtime_settings)

        analysis_data = data.get("analysis", {})
        analysis = AnalysisConfig.from_dict(analysis_data)

        return cls(
            stocks=stocks,
            email=email,
            analysis=analysis,
        )

    @classmethod
    def from_runtime(cls, runtime_settings: RuntimeSettings) -> AppConfig:
        """Load Invest configuration through the unified runtime settings."""
        return load_config(get_config_path(runtime_settings), runtime_settings=runtime_settings)


def load_config(
    config_path: Path | None = None,
    runtime_settings: RuntimeSettings | None = None,
) -> AppConfig:
    """Load configuration from YAML file.

    Loads configuration from the specified path or unified runtime settings path.
    Runtime setting GMAIL_APP_PASSWORD overrides email.password in config.

    Args:
        config_path: Optional custom config file path. Uses runtime settings if None.

    Returns:
        AppConfig instance with loaded configuration.

    Raises:
        ConfigError: If config file does not exist or is invalid.
    """
    runtime_settings = runtime_settings or get_runtime_settings()
    path = config_path or get_config_path(runtime_settings)

    if not path.exists():
        raise ConfigError(
            f"Configuration file not found: {path}\n"
            f"Please create a config file at {path} with the following structure:\n"
            f"""
stocks:
  - code: sh600519
    name: Guizhou Moutai
email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  sender: your_email@gmail.com
  recipient: your_email@gmail.com
analysis:
  start_time: "07:30"
  timezone: "Asia/Shanghai"
"""
        )

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file {path}: {e}") from e

    return AppConfig.from_dict(data, runtime_settings=runtime_settings)


def get_config_path(runtime_settings: RuntimeSettings | None = None) -> Path:
    """Get the default configuration file path.

    Returns:
        Path to configured py-invest config YAML.
    """
    runtime_settings = runtime_settings or get_runtime_settings()
    return runtime_settings.invest_config_path
