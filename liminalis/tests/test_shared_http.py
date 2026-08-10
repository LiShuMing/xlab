from __future__ import annotations

import httpx
import pytest

from backend._shared.http import (
    HTTPClientConfig,
    SharedAsyncHTTPClient,
    SharedCachedSyncHTTPClient,
    SharedSyncHTTPClient,
    fetch_text,
)
from backend.settings import Settings


def test_http_client_config_from_settings() -> None:
    settings = Settings(
        http_max_connections=8,
        http_max_keepalive=20,
        http_timeout=11.0,
    )

    config = HTTPClientConfig.from_settings(settings, read_timeout=22.0, follow_redirects=True)

    assert config.max_connections == 8
    assert config.max_keepalive_connections == 8
    assert config.max_concurrency == 4
    assert config.timeout.read == 22.0
    assert config.follow_redirects is True


@pytest.mark.asyncio
async def test_shared_async_http_client_uses_transport_and_base_url() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    client = SharedAsyncHTTPClient(
        HTTPClientConfig(max_connections=2, max_keepalive_connections=1, max_concurrency=1),
        base_url="https://example.test",
        headers={"X-Test": "shared"},
        transport=httpx.MockTransport(handler),
    )

    try:
        response = await client.get("/status")
    finally:
        await client.close()

    assert response.json() == {"ok": True}
    assert requests[0].url == "https://example.test/status"
    assert requests[0].headers["x-test"] == "shared"


@pytest.mark.asyncio
async def test_fetch_text_decodes_with_shared_async_client() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="价格".encode("gbk"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await fetch_text("https://example.test/quote", client=client, encoding="gbk")

    assert response.status_code == 200
    assert response.text == "价格"


def test_shared_sync_http_client_uses_transport_and_base_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    with SharedSyncHTTPClient(
        HTTPClientConfig(max_connections=2, max_keepalive_connections=1),
        base_url="https://example.test",
        headers={"X-Test": "shared"},
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.get("/status")

    assert response.json() == {"ok": True}
    assert requests[0].url == "https://example.test/status"
    assert requests[0].headers["x-test"] == "shared"


def test_shared_cached_sync_http_client_uses_hishel_transport(tmp_path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            text="cached",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    transport = httpx.MockTransport(handler)
    cache_db_path = tmp_path / "http.sqlite"

    for _ in range(2):
        with SharedCachedSyncHTTPClient(
            HTTPClientConfig(max_connections=2, max_keepalive_connections=1),
            cache_db_path=cache_db_path,
            transport=transport,
        ) as client:
            response = client.get("https://example.test/status")
            assert response.text == "cached"

    assert len(requests) == 1
    assert cache_db_path.exists()
