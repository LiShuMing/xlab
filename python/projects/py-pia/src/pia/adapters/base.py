"""Abstract base class for all source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pia.models.product import Product, ProductSource
from pia.models.release import Release


class BaseAdapter(ABC):
    """Base class for all source adapters.

    Each adapter knows how to fetch release metadata and content from a
    specific type of source (GitHub releases API, HTML docs page, RSS, etc.).
    """

    @abstractmethod
    async def fetch_releases(
        self, product: Product, source: ProductSource
    ) -> list[Release]:
        """Fetch a list of releases from the given source.

        Args:
            product: The product configuration.
            source: The specific source to query.

        Returns:
            List of Release objects discovered from this source.
        """
        pass

    @abstractmethod
    async def fetch_release_content(self, release: Release) -> str:
        """Fetch the raw content (HTML or markdown) for a specific release.

        Args:
            release: The release whose content should be fetched.

        Returns:
            Raw content string (HTML or markdown).
        """
        pass
