"""Fetch content from URLs with caching and error handling."""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional

import httpx
from tqdm import tqdm

from dbradar.cache import Cache, get_cache
from dbradar.sources import Source


@dataclass
class FetchResult:
    """Result of a fetch operation."""

    url: str
    product: str
    content: str
    content_type: str  # "html", "rss", "error"
    status_code: Optional[int]
    error_message: Optional[str] = None
    is_cached: bool = False


class Fetcher:
    """Fetch content from multiple URLs with caching."""

    def __init__(
        self,
        cache: Optional[Cache] = None,
        timeout: float = 30.0,
        max_concurrent: int = 5,
    ):
        self.cache = cache or get_cache()
        self.timeout = timeout
        self.max_concurrent = max_concurrent

    def _is_rss_url(self, url: str) -> bool:
        """Check if URL likely points to an RSS/Atom feed."""
        rss_patterns = [
            r"/feed",
            r"/rss",
            r"\.rss",
            r"\.atom",
            r"feed\.xml",
            r"index\.xml",
        ]
        return any(re.search(p, url, re.IGNORECASE) for p in rss_patterns)

    def _fetch_single(self, client: httpx.Client, url: str) -> FetchResult:
        """Fetch a single URL."""
        try:
            headers = {}
            entry = self.cache.get(url)

            if entry and entry.etag:
                headers["If-None-Match"] = entry.etag
            if entry and entry.last_modified:
                headers["If-Modified-Since"] = entry.last_modified

            response = client.get(url, headers=headers, timeout=self.timeout)
            content_hash = self.cache.get_content_hash(response.text)

            # Check if content changed (or 304 Not Modified)
            if entry and entry.content_hash == content_hash:
                return FetchResult(
                    url=url,
                    product="",  # Set by caller
                    content=entry.content,
                    content_type="rss" if self._is_rss_url(url) else "html",
                    status_code=response.status_code,
                    is_cached=True,
                )

            if response.status_code == 304:
                # Not modified, use cached content
                return FetchResult(
                    url=url,
                    product="",
                    content=entry.content if entry else "",
                    content_type="rss" if self._is_rss_url(url) else "html",
                    status_code=304,
                    is_cached=True,
                )

            if response.status_code >= 400:
                return FetchResult(
                    url=url,
                    product="",
                    content="",
                    content_type="error",
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                )

            # Store in cache
            self.cache.set(
                url=url,
                content=response.text,
                content_hash=content_hash,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                status_code=response.status_code,
            )

            return FetchResult(
                url=url,
                product="",
                content=response.text,
                content_type="rss" if self._is_rss_url(url) else "html",
                status_code=response.status_code,
                is_cached=False,
            )

        except httpx.TimeoutException:
            return FetchResult(
                url=url,
                product="",
                content="",
                content_type="error",
                status_code=None,
                error_message="Request timeout",
            )
        except httpx.RequestError as e:
            return FetchResult(
                url=url,
                product="",
                content="",
                content_type="error",
                status_code=None,
                error_message=f"Request error: {str(e)}",
            )
        except Exception as e:
            return FetchResult(
                url=url,
                product="",
                content="",
                content_type="error",
                status_code=None,
                error_message=f"Unexpected error: {str(e)}",
            )

    def fetch_source(self, source: Source, use_cache: bool = True) -> List[FetchResult]:
        """
        Fetch all URLs for a source.

        Args:
            source: Source object containing product name and URLs.
            use_cache: Whether to use cached content if available.

        Returns:
            List of FetchResult objects.
        """
        results = []

        # Filter URLs that don't need refresh
        urls_to_fetch = []
        if use_cache:
            for url in source.urls:
                if self.cache.is_stale(url):
                    urls_to_fetch.append(url)
        else:
            urls_to_fetch = source.urls

        # Use cached content for fresh entries
        for url in source.urls:
            if url in urls_to_fetch:
                continue
            entry = self.cache.get(url)
            if entry:
                results.append(
                    FetchResult(
                        url=url,
                        product=source.product,
                        content=entry.content,
                        content_type="rss" if self._is_rss_url(url) else "html",
                        status_code=entry.status_code,
                        is_cached=True,
                    )
                )

        if not urls_to_fetch:
            return results

        # Fetch remaining URLs
        with httpx.Client(timeout=self.timeout) as client:
            for url in tqdm(urls_to_fetch, desc=f"Fetching {source.product}"):
                result = self._fetch_single(client, url)
                result.product = source.product
                results.append(result)

        return results

    def fetch_all(
        self, sources: List[Source], use_cache: bool = True
    ) -> List[FetchResult]:
        """
        Fetch content from all sources.

        Args:
            sources: List of Source objects.
            use_cache: Whether to use cached content.

        Returns:
            List of all FetchResult objects.
        """
        all_results = []
        for source in sources:
            results = self.fetch_source(source, use_cache=use_cache)
            all_results.extend(results)
        return all_results


def fetch_sources(sources: List[Source], use_cache: bool = True) -> List[FetchResult]:
    """
    Convenience function to fetch all sources.

    Args:
        sources: List of Source objects.
        use_cache: Whether to use cached content.

    Returns:
        List of FetchResult objects.
    """
    fetcher = Fetcher()
    return fetcher.fetch_all(sources, use_cache=use_cache)


if __name__ == "__main__":
    # Quick test
    from dbradar.sources import get_sources
    from dbradar.config import get_config

    config = get_config()
    config.ensure_dirs()

    sources = get_sources()
    print(f"Found {len(sources)} sources")
    results = fetch_sources(sources[:2], use_cache=False)
    for r in results:
        print(f"  {r.url}: {r.status_code} ({'cached' if r.is_cached else 'fetched'})")
