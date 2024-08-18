"""Web search client for fact verification and competitive analysis.

Supports multiple providers:
- Tavily (recommended for RAG features)
- Serper (cheaper, Google Search API)
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


@dataclass
class SearchResult:
    """A single search result."""

    url: str
    title: str
    snippet: str
    source: str = ""  # Domain name

    @classmethod
    def from_tavily(cls, data: dict) -> "SearchResult":
        """Create from Tavily API response."""
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            snippet=data.get("content", ""),
            source=_extract_domain(data.get("url", "")),
        )

    @classmethod
    def from_serper(cls, data: dict) -> "SearchResult":
        """Create from Serper API response."""
        return cls(
            url=data.get("link", ""),
            title=data.get("title", ""),
            snippet=data.get("snippet", ""),
            source=_extract_domain(data.get("link", "")),
        )


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


class WebSearchClient(ABC):
    """Abstract base class for web search clients."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        """Search the web and return results.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects.
        """
        ...


class TavilyClient(WebSearchClient):
    """Tavily API client for web search."""

    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY not set")

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        """Search using Tavily API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "include_raw_content": False,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        return [SearchResult.from_tavily(r) for r in results[:max_results]]


class SerperClient(WebSearchClient):
    """Serper API client (Google Search)."""

    BASE_URL = "https://google.serper.dev"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY not set")

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        """Search using Serper API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/search",
                headers={"X-API-KEY": self.api_key},
                json={"q": query, "num": max_results},
            )
            response.raise_for_status()
            data = response.json()

        # Serper returns organic results
        results = data.get("organic", [])
        return [SearchResult.from_serper(r) for r in results[:max_results]]


class MockWebSearchClient(WebSearchClient):
    """Mock client for testing without API keys."""

    async def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        """Return mock results."""
        return [
            SearchResult(
                url=f"https://example.com/result/{i}",
                title=f"Mock Result {i} for: {query}",
                snippet=f"This is a mock search result for testing purposes. Query: {query}",
                source="example.com",
            )
            for i in range(min(max_results, 3))
        ]


def create_web_search_client(
    provider: str | None = None,
    api_key: str | None = None,
) -> WebSearchClient:
    """Create a web search client based on configuration.

    Args:
        provider: Provider name ("tavily", "serper", or "mock").
            Defaults to WEB_SEARCH_PROVIDER env var, or "tavily".
        api_key: API key for the provider.
            Defaults to provider-specific env var.

    Returns:
        Configured WebSearchClient instance.
    """
    provider = provider or os.environ.get("WEB_SEARCH_PROVIDER", "tavily").lower()

    if provider == "mock":
        log.info("using_mock_web_search")
        return MockWebSearchClient()

    if provider == "tavily":
        try:
            return TavilyClient(api_key)
        except ValueError:
            log.warning("tavily_key_missing_using_mock")
            return MockWebSearchClient()

    if provider == "serper":
        try:
            return SerperClient(api_key)
        except ValueError:
            log.warning("serper_key_missing_using_mock")
            return MockWebSearchClient()

    raise ValueError(f"Unknown web search provider: {provider}")