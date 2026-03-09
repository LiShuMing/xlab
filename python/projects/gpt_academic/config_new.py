"""
Modern Configuration Module for GPT Academic

Configuration loading priority (highest to lowest):
1. Environment variables (GPT_ACADEMIC_* prefix)
2. config_private.py (user overrides, git-ignored)
3. config.py (defaults)

Example:
    >>> from config_new import get_config
    >>> config = get_config()
    >>> print(config.llm.model)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger


@dataclass
class LLMConfig:
    """LLM-related configuration."""
    
    model: str = "gpt-4o-mini"
    """Default model to use for chat completions."""
    
    available_models: List[str] = field(default_factory=lambda: [
        # OpenAI models
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
        "o1-preview", "o1-mini", "o3-mini",
        # Anthropic models  
        "claude-3-opus-20240229", "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307", "claude-3-5-sonnet-20240620",
        # Qwen models
        "qwen-max", "qwen-plus", "qwen-turbo", "qwen3.5-plus",
        "dashscope-qwen3-32b", "dashscope-qwen3-14b",
    ])
    """List of available models in the UI."""
    
    temperature: float = 0.7
    """Sampling temperature (0.0 - 2.0)."""
    
    max_tokens: Optional[int] = None
    """Maximum tokens per response. None = model default."""
    
    timeout: float = 60.0
    """Request timeout in seconds."""


@dataclass
class APIKeys:
    """API key configuration for different providers."""
    
    openai: str = ""
    """OpenAI API key (or compatible)."""
    
    anthropic: str = ""
    """Anthropic API key for Claude models."""
    
    qwen: str = ""
    """Qwen/DashScope API key."""
    
    dashscope: str = ""
    """Legacy DashScope API key (fallback for qwen)."""


@dataclass
class ServerConfig:
    """Web server configuration."""
    
    port: int = -1
    """Server port. -1 for random port."""
    
    host: str = "0.0.0.0"
    """Server bind address."""
    
    auto_open_browser: bool = True
    """Automatically open browser on startup."""
    
    custom_path: str = "/"
    """Base path for the application (e.g., /gpt_academic)."""


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    
    enabled: bool = False
    """Whether to use proxy for API requests."""
    
    http: str = ""
    """HTTP proxy URL."""
    
    https: str = ""
    """HTTPS proxy URL."""
    
    @property
    def proxies(self) -> Optional[Dict[str, str]]:
        """Get proxies dict for requests/httpx."""
        if not self.enabled:
            return None
        return {
            "http": self.http or self.https,
            "https": self.https or self.http,
        }


@dataclass
class UIConfig:
    """User interface configuration."""
    
    theme: str = "Default"
    """UI theme name."""
    
    dark_mode: bool = True
    """Enable dark mode by default."""
    
    layout: str = "LEFT-RIGHT"
    """Layout mode: LEFT-RIGHT or TOP-DOWN."""
    
    chat_height: int = 1115
    """Chat window height (for TOP-DOWN layout)."""
    
    code_highlight: bool = True
    """Enable code syntax highlighting."""
    
    language: str = "auto"
    """UI language (auto, zh, en)."""


@dataclass
class AdvancedConfig:
    """Advanced configuration options."""
    
    plugin_hot_reload: bool = False
    """Enable plugin hot reloading (development)."""
    
    debug_mode: bool = False
    """Enable debug logging."""
    
    concurrent_workers: int = 8
    """Number of concurrent workers for multi-thread plugins."""
    
    max_retry: int = 2
    """Max retries on API failure."""
    
    allow_reset_config: bool = False
    """Allow natural language config modification (security risk)."""


@dataclass
class AppConfig:
    """Main application configuration container."""
    
    llm: LLMConfig = field(default_factory=LLMConfig)
    api_keys: APIKeys = field(default_factory=APIKeys)
    server: ServerConfig = field(default_factory=ServerConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    
    # Paths
    private_upload_path: str = "private_upload"
    log_path: str = "gpt_log"
    arxiv_cache_path: str = "gpt_log/arxiv_cache"
    
    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment variables."""
        config = cls()
        
        # LLM config
        if model := os.getenv("GPT_ACADEMIC_LLM_MODEL"):
            config.llm.model = model
        if models := os.getenv("GPT_ACADEMIC_AVAIL_LLM_MODELS"):
            import json
            try:
                config.llm.available_models = json.loads(models)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AVAIL_LLM_MODELS: {models}")
        
        # API Keys
        config.api_keys.openai = os.getenv("OPENAI_API_KEY", "")
        config.api_keys.anthropic = os.getenv("ANTHROPIC_API_KEY", "")
        config.api_keys.qwen = os.getenv("QWEN_API_KEY", "")
        config.api_keys.dashscope = os.getenv("DASHSCOPE_API_KEY", "")
        
        # Server config
        if port := os.getenv("GPT_ACADEMIC_WEB_PORT"):
            config.server.port = int(port)
        if host := os.getenv("GPT_ACADEMIC_WEB_HOST"):
            config.server.host = host
        
        # Proxy config
        if use_proxy := os.getenv("GPT_ACADEMIC_USE_PROXY"):
            config.proxy.enabled = use_proxy.lower() == "true"
        
        return config
    
    def validate(self) -> List[str]:
        """
        Validate configuration and return list of issues.
        
        Returns:
            List of validation error messages (empty if valid).
        """
        issues = []
        
        # Check if default model is in available models
        if self.llm.model not in self.llm.available_models:
            issues.append(
                f"Default model '{self.llm.model}' not in available models list. "
                f"Add it to AVAIL_LLM_MODELS or change LLM_MODEL."
            )
        
        # Check temperature range
        if not 0.0 <= self.llm.temperature <= 2.0:
            issues.append(f"Temperature must be in [0.0, 2.0], got {self.llm.temperature}")
        
        return issues


# Global config instance
_config: Optional[AppConfig] = None


def load_config() -> AppConfig:
    """
    Load configuration from all sources.
    
    Priority:
    1. Environment variables
    2. config_private.py
    3. config.py (defaults)
    
    Returns:
        Loaded AppConfig instance
    """
    global _config
    
    if _config is not None:
        return _config
    
    # Start with defaults
    config = AppConfig()
    
    # Override with config.py if exists
    try:
        import config as config_defaults
        _apply_module_config(config, config_defaults)
    except ImportError:
        logger.debug("config.py not found, using defaults")
    
    # Override with config_private.py if exists
    try:
        import config_private
        _apply_module_config(config, config_private)
        logger.info("Loaded user configuration from config_private.py")
    except ImportError:
        pass
    
    # Override with environment variables
    config = AppConfig.from_env()
    
    # Validate
    if issues := config.validate():
        for issue in issues:
            logger.warning(f"Config validation: {issue}")
    
    _config = config
    return config


def _apply_module_config(config: AppConfig, module: Any) -> None:
    """Apply configuration from a Python module."""
    # Map legacy config names to new structure
    mappings = {
        "LLM_MODEL": ("llm", "model"),
        "AVAIL_LLM_MODELS": ("llm", "available_models"),
        "TEMPERATURE": ("llm", "temperature"),
        "API_KEY": ("api_keys", "openai"),
        "ANTHROPIC_API_KEY": ("api_keys", "anthropic"),
        "QWEN_API_KEY": ("api_keys", "qwen"),
        "DASHSCOPE_API_KEY": ("api_keys", "dashscope"),
        "WEB_PORT": ("server", "port"),
        "USE_PROXY": ("proxy", "enabled"),
        "THEME": ("ui", "theme"),
        "DARK_MODE": ("ui", "dark_mode"),
        "LAYOUT": ("ui", "layout"),
    }
    
    for old_name, (section, field_name) in mappings.items():
        if hasattr(module, old_name):
            value = getattr(module, old_name)
            section_obj = getattr(config, section)
            if hasattr(section_obj, field_name):
                setattr(section_obj, field_name, value)


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    if _config is None:
        return load_config()
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from all sources."""
    global _config
    _config = None
    return load_config()


# Convenience exports
__all__ = [
    "AppConfig",
    "LLMConfig",
    "APIKeys",
    "ServerConfig",
    "ProxyConfig",
    "UIConfig",
    "AdvancedConfig",
    "load_config",
    "get_config",
    "reload_config",
]
