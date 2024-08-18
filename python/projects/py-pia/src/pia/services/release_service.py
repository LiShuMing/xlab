"""Release discovery and management service."""

from __future__ import annotations

import structlog

from pia.adapters.docs_html import DocsHtmlAdapter
from pia.adapters.github_releases import GitHubReleasesAdapter
from pia.exceptions import RateLimitError, ReleaseError, ReleaseFetchError
from pia.models.product import Product
from pia.models.release import Release
from pia.store.repositories import ReleaseRepository
from pia.telemetry import get_context_dict

logger = structlog.get_logger()


class ReleaseService:
    """Orchestrates release fetching across multiple source adapters."""

    def __init__(self) -> None:
        self.repo = ReleaseRepository()
        self.adapters = {
            "github_releases": GitHubReleasesAdapter(),
            "docs_html": DocsHtmlAdapter(),
        }

    async def sync_product(self, product: Product) -> list[Release]:
        """Fetch and upsert all releases for a product from all its sources.

        Sources are queried in priority order (highest first). Duplicate
        versions are merged by (product_id, version) uniqueness in the DB.

        Args:
            product: Product whose releases should be synced.

        Returns:
            Combined list of all fetched releases across all sources.

        Raises:
            RateLimitError: If API rate limit is exceeded.
            ReleaseFetchError: If fetching fails for all sources.
        """
        context = get_context_dict()
        all_releases: list[Release] = []
        any_success = False

        for source in sorted(product.sources, key=lambda s: s.priority, reverse=True):
            adapter = self.adapters.get(source.type)
            if not adapter:
                logger.warning(
                    "unknown adapter type",
                    product=product.id,
                    source_type=source.type,
                    **context,
                )
                continue
            try:
                releases = await adapter.fetch_releases(product, source)
                for r in releases:
                    self.repo.upsert(r)
                all_releases.extend(releases)
                any_success = True
                logger.info(
                    "source synced",
                    product=product.id,
                    source_type=source.type,
                    count=len(releases),
                    **context,
                )
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "sync failed",
                    product=product.id,
                    source_type=source.type,
                    error=error_msg,
                    **context,
                )
                # Re-raise rate-limit errors so the CLI can show a clear message
                if "rate limit" in error_msg.lower():
                    raise RateLimitError(
                        product_id=product.id,
                        source_type=source.type,
                        source_url=source.url,
                    ) from e

        if not any_success and product.sources:
            raise ReleaseFetchError(
                "Failed to fetch releases from all sources",
                product_id=product.id,
                source_type="multiple",
                source_url=str([s.url for s in product.sources]),
            )

        return all_releases

    def get_latest(self, product_id: str) -> Release | None:
        """Return the latest release for a product by semantic version.

        Args:
            product_id: Product identifier.

        Returns:
            Latest Release or None if no releases exist.
        """
        return self.repo.get_latest_by_product(product_id)

    def list_versions(self, product_id: str, limit: int = 20) -> list[Release]:
        """Return a list of releases for a product, newest first.

        Args:
            product_id: Product identifier.
            limit: Maximum number of releases to return.

        Returns:
            List of Release instances.
        """
        return self.repo.list_by_product(product_id, limit=limit)

    def get_by_version(self, product_id: str, version: str) -> Release | None:
        """Retrieve a specific release by version string.

        Args:
            product_id: Product identifier.
            version: Version string (will be normalized).

        Returns:
            Release or None if not found.
        """
        return self.repo.get_by_product_version(product_id, version)
