"""Radar cache compatibility wrapper backed by shared web cache."""

from backend._shared.web_cache import Cache, CacheEntry


def get_cache() -> Cache:
    """Get the default cache instance."""
    from backend._shared.storage import runtime_cache_path

    return Cache(runtime_cache_path("radar"))


__all__ = ["Cache", "CacheEntry", "get_cache"]
