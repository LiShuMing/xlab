"""Enhanced data sources from external APIs (Google Search, NewsAPI, etc.)."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from dbradar.config import get_config


@dataclass
class EnhancedItem:
    """Item from external API sources."""

    title: str
    url: str
    source: str  # e.g., "google_search", "newsapi"
    published_at: Optional[str] = None
    snippet: str = ""
    product: str = ""


class GoogleSearchSource:
    """Google Custom Search API source."""

    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cx = cx or os.environ.get("GOOGLE_CX", "")  # Custom Search Engine ID
        self.client = httpx.Client(timeout=30)

    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.api_key and self.cx)

    def validate(self) -> tuple:
        """Validate API configuration by making a test request.
        
        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        if not self.api_key:
            return False, "GOOGLE_API_KEY not set"
        if not self.cx:
            return False, "GOOGLE_CX (Search Engine ID) not set"
        
        try:
            response = self.client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": "test",
                    "num": 1,
                },
            )
            
            if response.status_code == 200:
                return True, "Google Custom Search API is working"
            elif response.status_code == 403:
                data = response.json()
                error = data.get("error", {}).get("message", "Unknown error")
                return False, f"API Error: {error}"
            elif response.status_code == 400:
                data = response.json()
                error = data.get("error", {}).get("message", "Unknown error")
                if "invalid" in error.lower():
                    return False, f"Invalid API Key or CX: {error}"
                return False, f"Bad Request: {error}"
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"
                
        except httpx.TimeoutException:
            return False, "Request timeout (network issue)"
        except Exception as e:
            return False, f"Exception: {str(e)}"

    def search(
        self,
        query: str,
        days: int = 7,
        max_results: int = 10,
    ) -> List[EnhancedItem]:
        """Search for recent content related to query."""
        if not self.is_configured():
            return []

        # Calculate date restriction (Google supports date restrict parameter)
        # d7 = past 7 days, d30 = past 30 days, etc.
        date_restrict = f"d{days}"

        try:
            response = self.client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "dateRestrict": date_restrict,
                    "num": min(max_results, 10),  # Google max is 10 per request
                    "sort": "date",  # Sort by date
                },
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for item in data.get("items", []):
                # Parse published date from metadata if available
                published_at = None
                if "pagemap" in item:
                    pagemap = item["pagemap"]
                    if "metatags" in pagemap:
                        metatags = pagemap["metatags"][0]
                        # Try common date fields
                        for key in ["article:published_time", "datePublished", "date", "DC.date"]:
                            if key in metatags:
                                published_at = metatags[key]
                                break

                items.append(
                    EnhancedItem(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        source="google_search",
                        published_at=published_at,
                        snippet=item.get("snippet", ""),
                        product=query.split()[0] if query else "",  # First word as product
                    )
                )
            return items

        except Exception:
            return []

    def search_products(
        self,
        products: List[str],
        keywords: List[str],
        days: int = 7,
        max_per_query: int = 5,
    ) -> List[EnhancedItem]:
        """Search for multiple products with keywords."""
        all_items = []
        for product in products:
            for keyword in keywords:
                query = f"{product} {keyword}"
                items = self.search(query, days=days, max_results=max_per_query)
                # Tag items with product
                for item in items:
                    item.product = product
                all_items.extend(items)
        return all_items


class NewsAPISource:
    """NewsAPI.org source."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("NEWSAPI_KEY", "")
        self.client = httpx.Client(timeout=30)

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    def validate(self) -> tuple:
        """Validate API configuration by making a test request.
        
        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        if not self.api_key:
            return False, "NEWSAPI_KEY not set"
        
        try:
            response = self.client.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "country": "us",
                    "pageSize": 1,
                    "apiKey": self.api_key,
                },
            )
            
            if response.status_code == 200:
                return True, "NewsAPI is working"
            elif response.status_code == 401:
                return False, "Invalid API Key (401 Unauthorized)"
            elif response.status_code == 429:
                return False, "Rate limit exceeded (too many requests)"
            else:
                data = response.json()
                error = data.get("message", response.text[:200])
                return False, f"API Error: {error}"
                
        except httpx.TimeoutException:
            return False, "Request timeout (network issue)"
        except Exception as e:
            return False, f"Exception: {str(e)}"

    def search(
        self,
        query: str,
        days: int = 7,
        max_results: int = 20,
    ) -> List[EnhancedItem]:
        """Search for news articles related to query."""
        if not self.is_configured():
            return []

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            response = self.client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "sortBy": "relevancy",
                    "pageSize": min(max_results, 100),
                    "apiKey": self.api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for article in data.get("articles", []):
                published_at = article.get("publishedAt")
                items.append(
                    EnhancedItem(
                        title=article.get("title", ""),
                        url=article.get("url", ""),
                        source=f"newsapi:{article.get('source', {}).get('name', 'unknown')}",
                        published_at=published_at,
                        snippet=article.get("description", ""),
                        product=query.split()[0] if query else "",
                    )
                )
            return items

        except Exception:
            return []

    def search_products(
        self,
        products: List[str],
        days: int = 7,
        max_per_product: int = 10,
    ) -> List[EnhancedItem]:
        """Search for news about multiple products."""
        all_items = []
        for product in products:
            # Search for product + database related news
            query = f"{product} database OR OLAP OR analytics"
            items = self.search(query, days=days, max_results=max_per_product)
            for item in items:
                item.product = product
            all_items.extend(items)
        return all_items


class EnhancedSourceManager:
    """Manager for all enhanced data sources."""

    # Default keywords to search for each product
    DEFAULT_KEYWORDS = [
        "release",
        "announcement",
        "performance",
        "optimization",
        "feature",
        "update",
        "benchmark",
    ]

    def __init__(self):
        self.google = GoogleSearchSource()
        self.newsapi = NewsAPISource()

    def get_configured_sources(self) -> List[str]:
        """Get list of configured source names."""
        sources = []
        if self.google.is_configured():
            sources.append("google_search")
        if self.newsapi.is_configured():
            sources.append("newsapi")
        return sources

    def fetch_all(
        self,
        products: List[str],
        days: int = 7,
        max_items_per_source: int = 20,
    ) -> List[EnhancedItem]:
        """Fetch from all configured sources."""
        all_items = []

        if self.google.is_configured():
            items = self.google.search_products(
                products=products,
                keywords=self.DEFAULT_KEYWORDS,
                days=days,
                max_per_query=3,
            )
            all_items.extend(items[:max_items_per_source])

        if self.newsapi.is_configured():
            items = self.newsapi.search_products(
                products=products,
                days=days,
                max_per_product=max_items_per_source // len(products) if products else 10,
            )
            all_items.extend(items[:max_items_per_source])

        return all_items

    def close(self):
        """Close all HTTP clients."""
        self.google.client.close()
        self.newsapi.client.close()

    def validate_all(self) -> dict:
        """Validate all configured sources.
        
        Returns:
            Dict mapping source name to (is_valid, message) tuple
        """
        results = {}
        
        # Always validate Google if key looks configured (even if partial)
        if self.google.api_key or self.google.cx:
            results["google_search"] = self.google.validate()
        else:
            results["google_search"] = (False, "Not configured (set GOOGLE_API_KEY and GOOGLE_CX)")
        
        # Always validate NewsAPI if key looks configured
        if self.newsapi.api_key:
            results["newsapi"] = self.newsapi.validate()
        else:
            results["newsapi"] = (False, "Not configured (set NEWSAPI_KEY)")
        
        return results


def get_enhanced_sources() -> EnhancedSourceManager:
    """Get configured enhanced source manager."""
    return EnhancedSourceManager()


def fetch_enhanced_items(
    products: List[str],
    days: int = 7,
    max_items: int = 40,
) -> List[EnhancedItem]:
    """Convenience function to fetch from all enhanced sources."""
    manager = get_enhanced_sources()
    try:
        return manager.fetch_all(
            products=products,
            days=days,
            max_items_per_source=max_items // 2,
        )
    finally:
        manager.close()


def validate_enhanced_sources() -> dict:
    """Validate all enhanced source configurations.
    
    Returns:
        Dict with validation results for each source
    """
    manager = get_enhanced_sources()
    try:
        return manager.validate_all()
    finally:
        manager.close()
