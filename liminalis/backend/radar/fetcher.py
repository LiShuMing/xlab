"""Radar fetcher compatibility wrapper backed by shared web fetcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tqdm import tqdm

from backend._shared.web_fetcher import FetchResult, FetchTarget, WebFetcher
from backend.radar.cache import Cache, get_cache
from backend.radar.sources import Source

if TYPE_CHECKING:
    from backend.radar.feeds import FeedSource


class Fetcher(WebFetcher):
    """Fetch Radar sources and feeds with shared URL fetching primitives."""

    USER_AGENT = "Mozilla/5.0 (compatible; LiminalisRadar/1.0; +https://github.com/xlab/liminalis)"

    def __init__(self, cache: Cache | None = None, timeout: float = 10.0):
        super().__init__(cache=cache or get_cache(), timeout=timeout)

    def fetch_source(self, source: Source, use_cache: bool = True) -> list[FetchResult]:
        """Fetch all URLs for a Radar source."""
        targets = [
            FetchTarget(
                url=url,
                product=source.product,
            )
            for url in source.urls
        ]
        return self.fetch_targets(
            targets,
            use_cache=use_cache,
            description=f"Fetching {source.product}",
        )

    def fetch_all(self, sources: list[Source], use_cache: bool = True) -> list[FetchResult]:
        """Fetch content from all Radar sources."""
        all_results = []
        for source in sources:
            results = self.fetch_source(source, use_cache=use_cache)
            all_results.extend(results)
        return all_results

    def fetch_feed(self, feed: FeedSource, use_cache: bool = True) -> FetchResult:
        """Fetch a single Radar feed source."""
        target = FetchTarget(
            url=feed.url,
            product=feed.title,
            filter_tags=feed.filter_tags,
            assume_rss=True,
        )
        return self.fetch_target(target, use_cache=use_cache)

    def fetch_feeds(self, feeds: list[FeedSource], use_cache: bool = True) -> list[FetchResult]:
        """Fetch content from multiple Radar feed sources."""
        all_results: list[FetchResult] = []
        feeds_to_fetch: list[FeedSource] = []

        for feed in feeds:
            target = FetchTarget(
                url=feed.url,
                product=feed.title,
                filter_tags=feed.filter_tags,
                assume_rss=True,
            )
            if use_cache and not self.cache.is_stale(feed.url):
                cached = self._cached_result(target, status_code=None)
                if cached is not None:
                    all_results.append(cached)
                    continue
            feeds_to_fetch.append(feed)

        if not feeds_to_fetch:
            return all_results

        with self._http_client() as client:
            for feed in tqdm(feeds_to_fetch, desc="Fetching feeds"):
                result = self._fetch_single(
                    client,
                    feed.url,
                    product=feed.title,
                    filter_tags=feed.filter_tags,
                    assume_rss=True,
                )
                all_results.append(result)

        return all_results


def fetch_sources(sources: list[Source], use_cache: bool = True) -> list[FetchResult]:
    """Convenience function to fetch all Radar sources."""
    fetcher = Fetcher()
    return fetcher.fetch_all(sources, use_cache=use_cache)


def fetch_feeds(feeds: list[FeedSource], use_cache: bool = True) -> list[FetchResult]:
    """Convenience function to fetch all Radar feed sources."""
    fetcher = Fetcher()
    return fetcher.fetch_feeds(feeds, use_cache=use_cache)


if __name__ == "__main__":
    from backend.radar.config import get_config
    from backend.radar.feeds import get_feeds

    config = get_config()
    config.ensure_dirs()

    feeds = get_feeds()
    if feeds:
        print(f"Found {len(feeds)} feed sources")
        results = fetch_feeds(feeds[:3], use_cache=False)
        for result in results:
            print(f"  {result.product}: {result.status_code} ({'cached' if result.is_cached else 'fetched'})")
            if result.filter_tags:
                print(f"    Filter tags: {result.filter_tags}")
    else:
        from backend.radar.sources import get_sources

        sources = get_sources()
        print(f"Found {len(sources)} sources (websites.txt)")
        results = fetch_sources(sources[:2], use_cache=False)
        for result in results:
            print(f"  {result.url}: {result.status_code} ({'cached' if result.is_cached else 'fetched'})")


__all__ = ["FetchResult", "Fetcher", "fetch_feeds", "fetch_sources"]
