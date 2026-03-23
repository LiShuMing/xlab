"""HTTP fetch service with disk caching."""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

from pia.config.settings import get_settings
from pia.telemetry.metrics import timed_tool_execution
from pia.utils.hashing import hash_url

logger = structlog.get_logger()


class FetchService:
    """Downloads and caches raw HTML/content from URLs.

    Fetched content is persisted to the raw data directory keyed by a hash
    of the URL. Subsequent requests for the same URL use the cached file
    unless force=True.
    """

    async def fetch_url(self, url: str, force: bool = False) -> str:
        """Fetch URL content, caching result to disk.

        Args:
            url: URL to fetch.
            force: If True, bypass cache and re-fetch.

        Returns:
            Response body as a string.

        Raises:
            httpx.HTTPStatusError: If the server returns an error response.
        """
        settings = get_settings()
        cache_path = settings.raw_dir / f"{hash_url(url)}.html"

        if cache_path.exists() and not force:
            logger.debug("fetch cache hit", url=url, path=str(cache_path))
            return cache_path.read_text(encoding="utf-8", errors="replace")

        with timed_tool_execution("fetch_url"):
            logger.info("fetching url", url=url)
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                headers = {"User-Agent": "pia/1.0 (product intelligence agent)"}
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                content = resp.text

        cache_path.write_text(content, encoding="utf-8")
        logger.debug("fetch cached", url=url, path=str(cache_path))
        return content

    async def fetch_url_to_file(self, url: str, dest: Path, force: bool = False) -> Path:
        """Fetch URL and save content to a specific file path.

        Args:
            url: URL to fetch.
            dest: Destination file path.
            force: If True, re-fetch even if dest already exists.

        Returns:
            Path to the saved file.
        """
        if dest.exists() and not force:
            return dest

        with timed_tool_execution("fetch_url_to_file"):
            content = await self.fetch_url(url, force=force)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        return dest
