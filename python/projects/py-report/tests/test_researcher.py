"""Tests for src/researcher.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx

from src.exceptions import APIKeyMissingError, ResearcherError
from src.researcher import (
    _build_system_prompt,
    _get_api_key,
    generate_report_async,
)


class TestGetApiKey:
    def test_raises_if_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QWEN_API_KEY", raising=False)
        with pytest.raises(APIKeyMissingError):
            _get_api_key()

    def test_returns_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QWEN_API_KEY", "test-key")
        assert _get_api_key() == "test-key"


class TestBuildSystemPrompt:
    def test_contains_product_name(self, tmp_path: Path) -> None:
        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))
        result = _build_system_prompt("Claude API", "English", "deep", prompts_path)
        assert "Claude API" in result

    def test_contains_depth(self, tmp_path: Path) -> None:
        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))
        result = _build_system_prompt("GPT-4o", "English", "executive", prompts_path)
        assert "executive" in result


class TestGenerateReportAsync:
    @pytest.mark.asyncio
    async def test_successful_generation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("QWEN_API_KEY", "test-key")
        monkeypatch.setenv("QWEN_BASE_URL", "https://fake-api.example.com/v1")
        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))

        fake_response = {
            "choices": [{"message": {"content": "# Report\nThis is the report."}}]
        }

        with respx.mock:
            respx.post("https://fake-api.example.com/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=fake_response)
            )
            result = await generate_report_async(
                "Claude API", prompts_path=prompts_path
            )
        assert "Report" in result

    @pytest.mark.asyncio
    async def test_api_error_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("QWEN_API_KEY", "test-key")
        monkeypatch.setenv("QWEN_BASE_URL", "https://fake-api.example.com/v1")
        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))

        with respx.mock:
            respx.post("https://fake-api.example.com/v1/chat/completions").mock(
                return_value=httpx.Response(401, json={"error": "Unauthorized"})
            )
            with pytest.raises(ResearcherError):
                await generate_report_async("Claude API", prompts_path=prompts_path)

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("QWEN_API_KEY", raising=False)
        prompts_path = tmp_path / "p.json"
        prompts_path.write_text(json.dumps({"prompts": []}))
        with pytest.raises(APIKeyMissingError):
            await generate_report_async("Claude API", prompts_path=prompts_path)
