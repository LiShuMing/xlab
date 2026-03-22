"""Product management service."""

from pathlib import Path

import structlog

from pia.config.loader import load_all_products, load_product
from pia.models.product import Product
from pia.store.repositories import ProductRepository
from pia.utils.dates import now_utc

log = structlog.get_logger()


class ProductService:
    """Manages product catalog operations including YAML config loading."""

    def __init__(self) -> None:
        self.repo = ProductRepository()

    def sync_products_from_disk(self) -> list[Product]:
        """Load all YAML configs and upsert them into the database.

        This is called on application startup to keep the DB in sync
        with the products directory.

        Returns:
            List of all loaded Product instances.
        """
        products = load_all_products()
        for p in products:
            if not p.created_at:
                p.created_at = now_utc()
            self.repo.upsert(p)
        log.info("products synced from disk", count=len(products))
        return products

    def list_products(self) -> list[Product]:
        """Return all products from the database.

        Returns:
            List of Product instances.
        """
        return self.repo.list_all()

    def get_product(self, product_id: str) -> Product | None:
        """Retrieve a single product by ID.

        Checks both the database and in-memory loaded configs.

        Args:
            product_id: Product identifier.

        Returns:
            Product instance or None if not found.
        """
        # Try DB first
        product = self.repo.get_by_id(product_id)
        if product:
            # Enrich with full config (sources, analysis) from disk if available
            all_products = load_all_products()
            for p in all_products:
                if p.id == product_id:
                    return p
        return product

    def add_product(self, config_path: Path) -> Product:
        """Load a product from a YAML file and persist it.

        Args:
            config_path: Path to the product YAML config file.

        Returns:
            The loaded and persisted Product instance.
        """
        p = load_product(config_path)
        p.created_at = now_utc()
        self.repo.upsert(p)
        log.info("product added", product_id=p.id, name=p.name)
        return p

    def validate_product(self, product_id: str) -> dict[str, bool]:
        """Check that a product's source URLs are reachable.

        Args:
            product_id: Product identifier to validate.

        Returns:
            Dict mapping source URL to reachability status.
        """
        import asyncio
        import httpx

        product = self.get_product(product_id)
        if not product:
            return {}

        results: dict[str, bool] = {}

        async def check_url(url: str) -> bool:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                    resp = await client.head(
                        url,
                        headers={"User-Agent": "pia/1.0 (product intelligence agent)"},
                    )
                    return resp.status_code < 400
            except Exception:
                return False

        async def run_checks() -> None:
            for source in product.sources:
                ok = await check_url(source.url)
                results[source.url] = ok

        asyncio.run(run_checks())
        return results
