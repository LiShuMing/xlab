"""Release discovery and management service."""

import structlog

from pia.adapters.docs_html import DocsHtmlAdapter
from pia.adapters.github_releases import GitHubReleasesAdapter
from pia.models.product import Product
from pia.models.release import Release
from pia.store.repositories import ReleaseRepository

log = structlog.get_logger()


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
        """
        all_releases: list[Release] = []
        for source in sorted(product.sources, key=lambda s: s.priority, reverse=True):
            adapter = self.adapters.get(source.type)
            if not adapter:
                log.warning(
                    "unknown adapter type",
                    product=product.id,
                    source_type=source.type,
                )
                continue
            try:
                releases = await adapter.fetch_releases(product, source)
                for r in releases:
                    self.repo.upsert(r)
                all_releases.extend(releases)
                log.info(
                    "source synced",
                    product=product.id,
                    source_type=source.type,
                    count=len(releases),
                )
            except Exception as e:
                log.warning(
                    "sync failed",
                    product=product.id,
                    source_type=source.type,
                    error=str(e),
                )
                # Re-raise rate-limit errors so the CLI can show a clear message
                if "rate limit" in str(e).lower():
                    raise
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
