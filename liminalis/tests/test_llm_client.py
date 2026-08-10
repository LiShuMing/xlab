"""Unit tests for the shared OpenAI-compatible LLM client."""

from __future__ import annotations

import json

import httpx
import pytest

from backend._shared.llm import ChatMessage, LLMClient, LLMError, LLMRuntimeConfig, SyncLLMClient
from backend.settings import Settings


def _settings() -> Settings:
    return Settings(
        llm_api_key="test-key",
        llm_base_url="https://llm.example/v1",
        llm_model="test-model",
        llm_max_retries=1,
        llm_max_tokens=32,
    )


def _runtime_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        api_key="test-key",
        base_url="https://llm.example/v1",
        model="test-model",
        max_retries=1,
        max_tokens=32,
    )


@pytest.mark.asyncio
async def test_shared_llm_client_posts_openai_compatible_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["max_tokens"] == 32
        return httpx.Response(200, json={"choices": [{"message": {"content": " world "}}]})

    client = httpx.AsyncClient(
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer test-key"},
    )
    llm = LLMClient(_settings(), client=client)

    response = await llm.complete([ChatMessage(role="user", content="hello")])

    assert response.text == "world"
    assert response.raw["_meta"]["elapsed_seconds"] >= 0
    await llm.aclose()


@pytest.mark.asyncio
async def test_shared_llm_client_retries_transient_failures() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.AsyncClient(
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer test-key"},
    )
    llm = LLMClient(_settings(), client=client)

    response = await llm.complete([ChatMessage(role="user", content="hello")])

    assert response.text == "ok"
    assert calls == 2
    await llm.aclose()


@pytest.mark.asyncio
async def test_shared_llm_client_reports_malformed_response() -> None:
    client = httpx.AsyncClient(
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []})),
        headers={"Authorization": "Bearer test-key"},
    )
    llm = LLMClient(_settings(), client=client)

    with pytest.raises(LLMError):
        await llm.complete([ChatMessage(role="user", content="hello")])
    await llm.aclose()


def test_shared_sync_llm_client_posts_openai_compatible_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "sync"}]
        return httpx.Response(200, json={"choices": [{"message": {"content": " done "}}]})

    client = httpx.Client(
        base_url="https://llm.example/v1",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer test-key"},
    )
    llm = SyncLLMClient(_runtime_config(), client=client)

    response = llm.complete([ChatMessage(role="user", content="sync")])

    assert response.text == "done"
    llm.close()


def test_shared_sync_llm_client_defers_missing_key_error_until_request() -> None:
    llm = SyncLLMClient(LLMRuntimeConfig(api_key="", base_url="https://llm.example/v1"))

    with pytest.raises(LLMError, match="LLM_API_KEY"):
        llm.complete([ChatMessage(role="user", content="hello")])

    llm.close()
