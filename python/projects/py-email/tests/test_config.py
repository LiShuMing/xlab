"""Tests for application configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from my_email.config import (
    _create_settings,
    _load_from_env_file,
    Settings,
)


class TestLoadFromEnvFile:
    """Tests for _load_from_env_file helper function."""

    def test_load_existing_keys(self, tmp_path):
        """Load specific keys from env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=test-key
LLM_MODEL=qwen2.5:7b
OTHER_VAR=should_be_ignored
""")

        result = _load_from_env_file(env_file, ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"])

        assert result["LLM_BASE_URL"] == "http://localhost:11434/v1"
        assert result["LLM_API_KEY"] == "test-key"
        assert result["LLM_MODEL"] == "qwen2.5:7b"
        assert "OTHER_VAR" not in result

    def test_load_from_nonexistent_file(self, tmp_path):
        """Return empty dict if file doesn't exist."""
        env_file = tmp_path / "nonexistent.env"
        result = _load_from_env_file(env_file, ["KEY1", "KEY2"])
        assert result == {}

    def test_load_skips_comments_and_empty_lines(self, tmp_path):
        """Skip comments and empty lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
# This is a comment
LLM_BASE_URL=http://localhost:11434/v1

# Another comment
LLM_MODEL=test-model

""")

        result = _load_from_env_file(env_file, ["LLM_BASE_URL", "LLM_MODEL"])

        assert result["LLM_BASE_URL"] == "http://localhost:11434/v1"
        assert result["LLM_MODEL"] == "test-model"

    def test_load_handles_equals_in_value(self, tmp_path):
        """Handle values containing '=' character."""
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=key=with=equals")

        result = _load_from_env_file(env_file, ["API_KEY"])

        assert result["API_KEY"] == "key=with=equals"


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self):
        """Settings have sensible defaults."""
        settings = Settings()

        assert settings.gmail_max_results == 100
        assert settings.gmail_timeout == 60
        assert settings.llm_timeout == 120
        assert settings.log_level == "INFO"

    def test_log_level_validation_valid(self):
        """Valid log levels are accepted and normalized to uppercase."""
        settings = Settings(log_level="debug")
        assert settings.log_level == "DEBUG"

        settings = Settings(log_level="warning")
        assert settings.log_level == "WARNING"

    def test_log_level_validation_invalid(self):
        """Invalid log levels raise ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            Settings(log_level="invalid_level")

    def test_gmail_max_results_range(self):
        """gmail_max_results must be between 1 and 500."""
        with pytest.raises(ValueError):
            Settings(gmail_max_results=0)

        with pytest.raises(ValueError):
            Settings(gmail_max_results=501)

        # Valid values
        settings = Settings(gmail_max_results=1)
        assert settings.gmail_max_results == 1

        settings = Settings(gmail_max_results=500)
        assert settings.gmail_max_results == 500

    def test_gmail_timeout_range(self):
        """gmail_timeout must be between 10 and 300."""
        with pytest.raises(ValueError):
            Settings(gmail_timeout=5)

        with pytest.raises(ValueError):
            Settings(gmail_timeout=301)

    def test_llm_timeout_range(self):
        """llm_timeout must be between 30 and 600."""
        with pytest.raises(ValueError):
            Settings(llm_timeout=10)

        with pytest.raises(ValueError):
            Settings(llm_timeout=601)

    def test_settings_are_frozen(self):
        """Settings are immutable after creation."""
        settings = Settings()

        with pytest.raises(Exception):  # pydantic raises various exceptions for frozen models
            settings.log_level = "DEBUG"

    def test_path_fields_are_path_objects(self):
        """Path fields are converted to Path objects."""
        settings = Settings()

        assert isinstance(settings.gmail_credentials_file, Path)
        assert isinstance(settings.gmail_token_file, Path)
        assert isinstance(settings.db_path, Path)

    def test_custom_values(self):
        """Settings can be customized."""
        settings = Settings(
            gmail_filter_query="from:test@example.com",
            gmail_max_results=50,
            llm_model="gpt-4",
            log_level="ERROR",
        )

        assert settings.gmail_filter_query == "from:test@example.com"
        assert settings.gmail_max_results == 50
        assert settings.llm_model == "gpt-4"
        assert settings.log_level == "ERROR"


class TestCreateSettings:
    """Tests for _create_settings function with global env loading."""

    @patch("my_email.config._load_from_env_file")
    @patch.dict(os.environ, {}, clear=True)
    def test_global_env_overrides_defaults(self, mock_load):
        """Global ~/.env settings override defaults."""
        mock_load.return_value = {
            "LLM_BASE_URL": "http://global-ollama:11434/v1",
            "LLM_MODEL": "global-model",
        }

        settings = _create_settings()

        assert settings.llm_base_url == "http://global-ollama:11434/v1"
        assert settings.llm_model == "global-model"
        mock_load.assert_called_once()

    @patch("my_email.config._load_from_env_file")
    @patch.dict(os.environ, {"LLM_MODEL": "env-model"}, clear=True)
    def test_global_env_overrides_env_vars(self, mock_load):
        """Global ~/.env takes precedence over environment variables for LLM settings."""
        mock_load.return_value = {
            "LLM_MODEL": "global-model",
        }

        settings = _create_settings()

        # Global ~/.env wins for LLM settings (allows shared config across projects)
        assert settings.llm_model == "global-model"

    @patch("my_email.config._load_from_env_file")
    def test_no_override_if_global_env_empty(self, mock_load):
        """Don't override if global env values are empty."""
        mock_load.return_value = {
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
        }

        settings = _create_settings()

        # Should use defaults, not empty strings
        assert settings.llm_base_url == ""
        assert settings.llm_api_key == ""

    @patch("my_email.config._load_from_env_file")
    def test_llm_timeout_conversion(self, mock_load):
        """LLM_TIMEOUT is converted to int."""
        mock_load.return_value = {
            "LLM_TIMEOUT": "300",
        }

        settings = _create_settings()

        assert settings.llm_timeout == 300
        assert isinstance(settings.llm_timeout, int)

    @patch("my_email.config.Path")
    @patch("my_email.config._load_from_env_file")
    def test_global_env_file_path(self, mock_load, mock_path):
        """Global env file is loaded from ~/.env."""
        mock_load.return_value = {}
        mock_home = mock_path.home.return_value
        mock_home.__truediv__ = lambda self, x: Path(f"/home/user/{x}")

        _create_settings()

        # Check that ~/.env was used
        args = mock_load.call_args
        assert ".env" in str(args[0][0])
