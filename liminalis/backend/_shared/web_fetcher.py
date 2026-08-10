"""Shared URL fetcher with file cache and HTTP error handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import httpx
from tqdm import tqdm

from backend._shared.http import HTTPClientConfig, SharedCachedSyncHTTPClient, SharedSyncHTTPClient
from backend._shared.web_cache import Cache
from backend._shared.web_feed import detect_content_type, is_feed_url
from backend.settings import get_settings as get_runtime_settings


@dataclass
class FetchTarget:
    """Generic target consumed by the shared fetcher."""

    url: str
    product: str
    filter_tags: list[str] = field(default_factory=list)
    assume_rss: bool = False


@dataclass
class FetchResult:
    """Result of a fetch operation."""

    url: str
    product: str
    content: str
    content_type: str
    status_code: int | None
    error_message: str | None = None
    is_cached: bool = False
    filter_tags: list[str] | None = None

    def __post_init__(self) -> None:
        if self.filter_tags is None:
            self.filter_tags = []


class WebFetcher:
    """Fetch content from URLs with caching."""

    USER_AGENT = "Mozilla/5.0 (compatible; Liminalis/1.0; +https://github.com/xlab/liminalis)"

    def __init__(
        self,
        cache: Cache,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        enable_http_cache: bool = True,
        http_cache_path: str | Path | None = None,
        http_cache_ttl: float | None = 24 * 3600,
    ):
        self.cache = cache
        self.timeout = timeout
        self.transport = transport
        self.enable_http_cache = enable_http_cache
        self.http_cache_path = (
            Path(http_cache_path) if http_cache_path is not None else cache.cache_dir / "http.sqlite"
        )
        self.http_cache_ttl = http_cache_ttl

    def _http_client(self) -> SharedSyncHTTPClient:
        config = HTTPClientConfig.from_settings(
            get_runtime_settings(),
            read_timeout=self.timeout,
        )
        if self.enable_http_cache:
            return SharedCachedSyncHTTPClient(
                config,
                cache_db_path=self.http_cache_path,
                cache_ttl=self.http_cache_ttl,
                transport=self.transport,
            )
        return SharedSyncHTTPClient(config, transport=self.transport)

    def _is_rss_url(self, url: str) -> bool:
        """Check if URL likely points to an RSS/Atom feed."""
        return is_feed_url(url)

    def _content_type_for(
        self,
        url: str,
        assume_rss: bool = False,
        content: str | None = None,
    ) -> str:
        return detect_content_type(url, content, assume_feed=assume_rss)

    def _cached_result(self, target: FetchTarget, status_code: int | None) -> FetchResult | None:
        entry = self.cache.get(target.url)
        if entry is None:
            return None
        return FetchResult(
            url=target.url,
            product=target.product,
            content=entry.content,
            content_type=self._content_type_for(target.url, target.assume_rss, entry.content),
            status_code=status_code if status_code is not None else entry.status_code,
            is_cached=True,
            filter_tags=target.filter_tags,
        )

    def _fetch_single(
        self,
        client: httpx.Client,
        url: str,
        product: str,
        filter_tags: list[str] | None = None,
        assume_rss: bool = False,
    ) -> FetchResult:
        """Fetch a single URL."""
        target = FetchTarget(
            url=url,
            product=product,
            filter_tags=filter_tags or [],
            assume_rss=assume_rss,
        )
        try:
            headers = {"User-Agent": self.USER_AGENT}
            entry = self.cache.get(target.url)

            if entry and entry.etag:
                headers["If-None-Match"] = entry.etag
            if entry and entry.last_modified:
                headers["If-Modified-Since"] = entry.last_modified

            response = client.get(target.url, headers=headers, timeout=self.timeout)

            if response.status_code == 304:
                cached = self._cached_result(target, status_code=304)
                if cached is not None:
                    return cached

            if response.status_code >= 400:
                return FetchResult(
                    url=target.url,
                    product=target.product,
                    content="",
                    content_type="error",
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                    filter_tags=target.filter_tags,
                )

            content_type = self._content_type_for(target.url, target.assume_rss, response.text)
            content_hash = self.cache.get_content_hash(response.text)

            if entry and entry.content_hash == content_hash:
                cached = self._cached_result(target, status_code=response.status_code)
                if cached is not None:
                    return cached

            self.cache.set(
                url=target.url,
                content=response.text,
                content_hash=content_hash,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                status_code=response.status_code,
            )

            return FetchResult(
                url=target.url,
                product=target.product,
                content=response.text,
                content_type=content_type,
                status_code=response.status_code,
                is_cached=False,
                filter_tags=target.filter_tags,
            )

        except httpx.TimeoutException:
            return FetchResult(
                url=target.url,
                product=target.product,
                content="",
                content_type="error",
                status_code=None,
                error_message="Request timeout",
                filter_tags=target.filter_tags,
            )
        except httpx.RequestError as exc:
            return FetchResult(
                url=target.url,
                product=target.product,
                content="",
                content_type="error",
                status_code=None,
                error_message=f"Request error: {exc}",
                filter_tags=target.filter_tags,
            )
        except Exception as exc:
            return FetchResult(
                url=target.url,
                product=target.product,
                content="",
                content_type="error",
                status_code=None,
                error_message=f"Unexpected error: {exc}",
                filter_tags=target.filter_tags,
            )

    def fetch_target(self, target: FetchTarget, use_cache: bool = True) -> FetchResult:
        """Fetch one generic target."""
        if use_cache and not self.cache.is_stale(target.url):
            cached = self._cached_result(target, status_code=None)
            if cached is not None:
                return cached

        with self._http_client() as client:
            return self._fetch_single(
                client,
                target.url,
                product=target.product,
                filter_tags=target.filter_tags,
                assume_rss=target.assume_rss,
            )

    def fetch_targets(
        self,
        targets: list[FetchTarget],
        use_cache: bool = True,
        description: str = "Fetching",
    ) -> list[FetchResult]:
        """Fetch multiple generic targets."""
        results: list[FetchResult] = []
        targets_to_fetch: list[FetchTarget] = []

        for target in targets:
            if use_cache and not self.cache.is_stale(target.url):
                cached = self._cached_result(target, status_code=None)
                if cached is not None:
                    results.append(cached)
                    continue
            targets_to_fetch.append(target)

        if not targets_to_fetch:
            return results

        with self._http_client() as client:
            for target in tqdm(targets_to_fetch, desc=description):
                result = self._fetch_single(
                    client,
                    target.url,
                    product=target.product,
                    filter_tags=target.filter_tags,
                    assume_rss=target.assume_rss,
                )
                results.append(result)

        return results
