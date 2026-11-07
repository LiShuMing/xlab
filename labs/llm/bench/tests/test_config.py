"""Tests for config.py — configuration loading from ~/.env."""

from __future__ import annotations

import os

from llm_benchmark.config import BenchmarkConfig, ModelConfig, load_config


class TestLoadConfig:
    def test_defaults_when_no_env_file(self, temp_env_file, monkeypatch):
        """Config returns sensible defaults when no .env file exists."""
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        config = load_config()
        assert isinstance(config, BenchmarkConfig)
        assert config.default_model == ""

    def test_loads_basic_settings(self, temp_env_file, sample_env_content, monkeypatch):
        """Loads LLM_BASE_URL, LLM_API_KEY, LLM_MODEL from .env."""
        temp_env_file.write_text(sample_env_content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        config = load_config()

        assert config.default_model == "test-model"
        assert "test-model" in config.models
        model = config.models["test-model"]
        assert model.base_url == "https://api.example.com/v1"
        assert model.api_key == "sk-test-key-123"
        assert model.max_concurrent == 8
        assert model.timeout == 60.0
        assert model.max_tokens == 2048

    def test_loads_multi_model_configs(self, temp_env_file, sample_env_content, monkeypatch):
        """Loads LLM_MODEL_1, LLM_MODEL_2 multi-model configs."""
        temp_env_file.write_text(sample_env_content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        config = load_config()

        assert "model-a" in config.models
        assert "model-b" in config.models
        assert config.models["model-a"].base_url == "https://a.example.com/v1"
        assert config.models["model-a"].api_key == "key-a"
        assert config.models["model-b"].base_url == "https://b.example.com/v1"
        assert config.models["model-b"].api_key == "key-b"

    def test_env_var_overrides_file(self, temp_env_file, sample_env_content, monkeypatch):
        """Environment variables take precedence over .env file values."""
        temp_env_file.write_text(sample_env_content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        monkeypatch.setenv("LLM_BASE_URL", "https://override.example.com/v1")
        monkeypatch.setenv("LLM_MODEL", "overridden-model")

        config = load_config()
        assert config.default_model == "overridden-model"
        assert config.models["overridden-model"].base_url == "https://override.example.com/v1"

    def test_ignores_comments_and_blank_lines(self, temp_env_file, monkeypatch):
        """Ignores lines starting with # and blank lines."""
        content = """# This is a comment
LLM_MODEL=my-model

# Another comment
LLM_BASE_URL=https://api.example.com/v1
"""
        temp_env_file.write_text(content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        config = load_config()
        assert config.default_model == "my-model"
        assert config.models["my-model"].base_url == "https://api.example.com/v1"

    def test_quoted_values_are_stripped(self, temp_env_file, monkeypatch):
        """Values with quotes are stripped correctly."""
        temp_env_file.write_text('LLM_MODEL="quoted-model"\nLLM_BASE_URL=\'https://api.example.com/v1\'\n')
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        config = load_config()
        assert config.default_model == "quoted-model"
        assert config.models["quoted-model"].base_url == "https://api.example.com/v1"


class TestGetModelConfig:
    def test_returns_model_by_name(self, temp_env_file, sample_env_content, monkeypatch):
        temp_env_file.write_text(sample_env_content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        from llm_benchmark.config import get_model_config

        config = load_config()
        model = get_model_config(config, "model-a")
        assert model.name == "model-a"

    def test_falls_back_to_default(self, temp_env_file, sample_env_content, monkeypatch):
        temp_env_file.write_text(sample_env_content)
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        from llm_benchmark.config import get_model_config

        config = load_config()
        model = get_model_config(config, "nonexistent")
        assert model.name == "test-model"

    def test_raises_when_no_models(self, temp_env_file, monkeypatch):
        monkeypatch.setattr("llm_benchmark.config._env_path", lambda: temp_env_file)
        from llm_benchmark.config import get_model_config

        config = load_config()
        try:
            get_model_config(config)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass