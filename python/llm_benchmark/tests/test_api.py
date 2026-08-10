"""Tests for api/client.py and api/retry.py."""

from __future__ import annotations

import pytest

from llm_benchmark.api.client import APIResponse, LLMClient
from llm_benchmark.config import ModelConfig


@pytest.fixture
def model_config():
    return ModelConfig(
        name="test-model",
        base_url="https://api.example.com/v1",
        api_key="sk-test-key",
        max_concurrent=4,
        timeout=30.0,
        max_tokens=1024,
    )


@pytest.fixture
def client(model_config):
    return LLMClient(model_config)


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_chat_returns_response(self, client, httpx_mock):
        """A successful chat completion returns text, tokens, and latency."""
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            json={
                "choices": [
                    {"message": {"content": "Hello, world!"}, "finish_reason": "stop"}
                ],
                "usage": {"total_tokens": 42},
            },
        )

        resp = await client.chat(
            messages=[{"role": "user", "content": "Say hello"}],
        )

        assert isinstance(resp, APIResponse)
        assert resp.text == "Hello, world!"
        assert resp.token_usage == 42
        assert resp.latency_ms > 0

    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self, client, httpx_mock):
        """Verifies that the HTTP request body matches expected format."""
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 10},
            },
        )

        await client.chat(
            messages=[{"role": "user", "content": "test"}],
            model="test-model",
            temperature=0.0,
            max_tokens=2048,
            seed=42,
        )

        import json

        request = httpx_mock.get_request()
        body = json.loads(request.read())
        assert body["model"] == "test-model"
        assert body["temperature"] == 0.0
        assert body["max_tokens"] == 2048
        assert body["seed"] == 42
        assert body["messages"] == [{"role": "user", "content": "test"}]

    @pytest.mark.asyncio
    async def test_chat_retries_on_429(self, client, httpx_mock):
        """Retries on 429 Too Many Requests with exponential backoff."""
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            status_code=429,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            json={
                "choices": [{"message": {"content": "retried"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 5},
            },
        )

        resp = await client.chat(
            messages=[{"role": "user", "content": "test"}],
        )

        assert resp.text == "retried"

    @pytest.mark.asyncio
    async def test_chat_retries_on_timeout(self, client, httpx_mock):
        """Retries on timeout exceptions."""
        from httpx import TimeoutException

        httpx_mock.add_exception(TimeoutException("timeout"))
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            json={
                "choices": [{"message": {"content": "after timeout"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 5},
            },
        )

        resp = await client.chat(
            messages=[{"role": "user", "content": "test"}],
        )

        assert resp.text == "after timeout"

    @pytest.mark.asyncio
    async def test_chat_raises_on_non_retryable_error(self, client, httpx_mock):
        """Does not retry on non-retryable status codes (e.g. 400)."""
        httpx_mock.add_response(
            url="https://api.example.com/v1/chat/completions",
            method="POST",
            status_code=400,
            json={"error": {"message": "Bad request"}},
        )

        with pytest.raises(Exception):
            await client.chat(
                messages=[{"role": "user", "content": "test"}],
            )

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self, client):
        await client.close()
        assert client._client is None or client._client.is_closed