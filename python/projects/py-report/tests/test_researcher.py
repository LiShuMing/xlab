"""Tests for src/researcher.py and agent module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx

from src.exceptions import ResearcherError
from src.researcher import generate_report_async
from src.agent.tools.base_report import _get_api_key, _build_system_prompt


class TestGetApiKey:
    def test_raises_if_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError):
            _get_api_key()

    def test_returns_key_from_llm_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        assert _get_api_key() == "test-key"

    def test_returns_key_from_anthropic_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
        assert _get_api_key() == "anthropic-key"


class TestBuildSystemPrompt:
    def test_contains_product_name(self, tmp_path: Path) -> None:
        from src.agent.tools.base_report import _build_system_prompt

        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))
        result = _build_system_prompt("Claude API", "English", "deep", prompts_path)
        assert "Claude API" in result

    def test_contains_depth(self, tmp_path: Path) -> None:
        from src.agent.tools.base_report import _build_system_prompt

        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))
        result = _build_system_prompt("GPT-4o", "English", "executive", prompts_path)
        assert "executive" in result


class TestGenerateReportAsync:
    @pytest.mark.asyncio
    async def test_successful_generation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that generate_report_async returns a report string."""
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_BASE_URL", "https://fake-api.example.com/v1")

        # Mock the AsyncAnthropic client
        mock_message = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "# Report\nThis is the report."
        mock_message.content = [mock_block]

        with patch("src.agent.tools.base_report.AsyncAnthropic") as MockClient:
            mock_instance = MockClient.return_value.__aenter__.return_value
            mock_instance.messages.create = AsyncMock(return_value=mock_message)

            result = await generate_report_async("Claude API")
            assert "Report" in result

    @pytest.mark.asyncio
    async def test_api_error_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that API errors are wrapped in ResearcherError."""
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_BASE_URL", "https://fake-api.example.com/v1")

        with patch("src.agent.tools.base_report.AsyncAnthropic") as MockClient:
            mock_instance = MockClient.return_value.__aenter__.return_value
            mock_instance.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )

            with pytest.raises(ResearcherError):
                await generate_report_async("Claude API")

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that missing API key raises ResearcherError."""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ResearcherError):
            await generate_report_async("Claude API")