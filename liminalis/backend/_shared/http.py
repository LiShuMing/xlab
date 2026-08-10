"""Shared HTTP client primitives for Liminalis modules."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from backend.settings import Settings

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
HTTPError = httpx.HTTPError
TimeoutException = httpx.TimeoutException
Response = httpx.Response
AsyncClient = httpx.AsyncClient


def default_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


@dataclass(frozen=True)
class HTTPClientConfig:
    """Connection, timeout, and concurrency settings for shared HTTP clients."""

    max_connections: int = 20
    max_keepalive_connections: int = 10
    timeout: httpx.Timeout = field(default_factory=default_timeout)
    max_concurrency: int = 10
    follow_redirects: bool = False
    http2: bool = False

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        read_timeout: float | None = None,
        follow_redirects: bool = False,
    ) -> HTTPClientConfig:
        max_connections = max(settings.http_max_connections, 1)
        max_keepalive = min(max(settings.http_max_keepalive, 0), max_connections)
        read = float(read_timeout if read_timeout is not None else settings.http_timeout)
        return cls(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive,
            timeout=httpx.Timeout(connect=10.0, read=read, write=10.0, pool=5.0),
            max_concurrency=max(1, min(10, max_connections // 2 or 1)),
            follow_redirects=follow_redirects,
        )


@dataclass(frozen=True)
class TextResponse:
    """Normalized text response used by lightweight collectors."""

    url: str
    text: str
    status_code: int
    headers: dict[str, str]


def make_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    limits: httpx.Limits | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    follow_redirects: bool = False,
    http2: bool = False,
) -> httpx.AsyncClient:
    """Create a plain async httpx client with the shared defaults."""
    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "headers": headers or {},
        "timeout": timeout,
        "follow_redirects": follow_redirects,
        "http2": http2,
    }
    if limits is not None:
        kwargs["limits"] = limits
    if transport is not None:
        kwargs["transport"] = transport
    return httpx.AsyncClient(**kwargs)


async def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    encoding: str | None = None,
    follow_redirects: bool = True,
    client: httpx.AsyncClient | SharedAsyncHTTPClient | None = None,
) -> TextResponse:
    """Fetch a URL and return decoded text through the shared HTTP stack."""

    async def _read(response: httpx.Response) -> TextResponse:
        response.raise_for_status()
        if encoding:
            response.encoding = encoding
        return TextResponse(
            url=str(response.url),
            text=response.text,
            status_code=response.status_code,
            headers=dict(response.headers),
        )

    if client is not None:
        return await _read(
            await client.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        )

    async with make_client(
        headers=headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
    ) as managed_client:
        return await _read(await managed_client.get(url))


def make_unix_socket_client(
    *,
    socket_path: str | Path,
    base_url: str,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = False,
) -> httpx.AsyncClient:
    """Create an async client that talks HTTP over a Unix domain socket."""
    return make_client(
        base_url=base_url,
        headers=headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
        transport=httpx.AsyncHTTPTransport(uds=str(socket_path)),
    )


def make_sync_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    limits: httpx.Limits | None = None,
    transport: httpx.BaseTransport | None = None,
    follow_redirects: bool = False,
    http2: bool = False,
) -> httpx.Client:
    """Create a plain sync httpx client with the shared defaults."""
    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "headers": headers or {},
        "timeout": timeout,
        "follow_redirects": follow_redirects,
        "http2": http2,
    }
    if limits is not None:
        kwargs["limits"] = limits
    if transport is not None:
        kwargs["transport"] = transport
    return httpx.Client(**kwargs)


def make_cached_sync_client(
    *,
    cache_db_path: str | Path,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    limits: httpx.Limits | None = None,
    transport: httpx.BaseTransport | None = None,
    follow_redirects: bool = False,
    http2: bool = False,
    cache_ttl: float | None = None,
) -> httpx.Client:
    """Create a sync httpx client with RFC-aware persistent HTTP caching."""
    import hishel
    import hishel.httpx

    storage = hishel.SyncSqliteStorage(
        database_path=Path(cache_db_path),
        default_ttl=cache_ttl,
    )
    policy = hishel.SpecificationPolicy(
        cache_options=hishel.CacheOptions(
            supported_methods=["GET", "HEAD"],
            allow_stale=False,
        )
    )

    if transport is not None:
        cached_transport = hishel.httpx.SyncCacheTransport(
            next_transport=transport,
            storage=storage,
            policy=policy,
        )
        return make_sync_client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            limits=limits,
            transport=cached_transport,
            follow_redirects=follow_redirects,
            http2=http2,
        )

    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "headers": headers or {},
        "timeout": timeout,
        "follow_redirects": follow_redirects,
        "http2": http2,
        "storage": storage,
        "policy": policy,
    }
    if limits is not None:
        kwargs["limits"] = limits
    return hishel.httpx.SyncCacheClient(**kwargs)


class SharedAsyncHTTPClient:
    """Reusable async HTTP client with connection pooling and concurrency limits."""

    def __init__(
        self,
        config: HTTPClientConfig,
        *,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._base_url = base_url
        self._headers = headers or {}
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    @property
    def max_concurrency(self) -> int:
        return self._config.max_concurrency

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._config.max_connections,
                max_keepalive_connections=self._config.max_keepalive_connections,
            )
            self._client = make_client(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._config.timeout,
                limits=limits,
                transport=self._transport,
                follow_redirects=self._config.follow_redirects,
                http2=self._config.http2,
            )
        return self._client

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._ensure_client()
        async with self._semaphore:
            return await client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> SharedAsyncHTTPClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()


class SharedSyncHTTPClient:
    """Reusable sync HTTP client with shared connection pooling defaults."""

    def __init__(
        self,
        config: HTTPClientConfig,
        *,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._base_url = base_url
        self._headers = headers or {}
        self._transport = transport
        self._client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._config.max_connections,
                max_keepalive_connections=self._config.max_keepalive_connections,
            )
            self._client = make_sync_client(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._config.timeout,
                limits=limits,
                transport=self._transport,
                follow_redirects=self._config.follow_redirects,
                http2=self._config.http2,
            )
        return self._client

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self._ensure_client().request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> SharedSyncHTTPClient:
        self._ensure_client()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class SharedCachedSyncHTTPClient(SharedSyncHTTPClient):
    """Reusable sync HTTP client with shared pooling and persistent HTTP cache."""

    def __init__(
        self,
        config: HTTPClientConfig,
        *,
        cache_db_path: str | Path,
        cache_ttl: float | None = None,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            config,
            base_url=base_url,
            headers=headers,
            transport=transport,
        )
        self._cache_db_path = Path(cache_db_path)
        self._cache_ttl = cache_ttl

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._cache_db_path.parent.mkdir(parents=True, exist_ok=True)
            limits = httpx.Limits(
                max_connections=self._config.max_connections,
                max_keepalive_connections=self._config.max_keepalive_connections,
            )
            self._client = make_cached_sync_client(
                cache_db_path=self._cache_db_path,
                cache_ttl=self._cache_ttl,
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._config.timeout,
                limits=limits,
                transport=self._transport,
                follow_redirects=self._config.follow_redirects,
                http2=self._config.http2,
            )
        return self._client
