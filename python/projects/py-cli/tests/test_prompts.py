"""Tests for prompt templates."""

from __future__ import annotations

import pytest

from py_cli.exceptions import PromptNotFoundError
from py_cli.llm.prompts import get_prompt, list_prompts, register_prompt


class TestPrompts:
    """Tests for prompt module."""

    def test_list_prompts(self) -> None:
        """Test listing available prompts."""
        prompts = list_prompts()

        assert "default" in prompts
        assert "clickhouse" in prompts

    def test_get_default_prompt(self) -> None:
        """Test getting default prompt."""
        prompt = get_prompt("default")

        assert hasattr(prompt, "SYSTEM_PROMPT")
        assert hasattr(prompt, "USER_PROMPT_TEMPLATE")
        assert hasattr(prompt, "format_commit_details")

    def test_get_clickhouse_prompt(self) -> None:
        """Test getting clickhouse prompt."""
        prompt = get_prompt("clickhouse")

        assert hasattr(prompt, "SYSTEM_PROMPT")
        assert hasattr(prompt, "USER_PROMPT_TEMPLATE")

    def test_get_invalid_prompt_raises(self) -> None:
        """Test that invalid prompt name raises error."""
        with pytest.raises(PromptNotFoundError):
            get_prompt("nonexistent")

    def test_register_prompt(self) -> None:
        """Test registering a new prompt."""
        import types

        # Create a mock prompt module
        mock_module = types.ModuleType("mock_prompt")
        mock_module.SYSTEM_PROMPT = "System"
        mock_module.USER_PROMPT_TEMPLATE = "Template"

        register_prompt("mock", mock_module)

        # Should be able to retrieve it
        retrieved = get_prompt("mock")
        assert retrieved == mock_module
