"""Digest service: generate multi-product periodic digest reports."""

from __future__ import annotations

import uuid
from datetime import timedelta

import structlog

from pia.config.settings import get_settings
from pia.llm.provider import PROMPT_VERSION, LLMProvider
from pia.models.report import DigestReport
from pia.store.repositories import ReleaseRepository, ReportRepository
from pia.telemetry import correlation_context, get_context_dict
from pia.utils.dates import now_utc
from pia.utils.hashing import hash_content

logger = structlog.get_logger()


class DigestService:
    """Generates multi-product digest reports over a configurable time window."""

    def __init__(self, model: str | None = None) -> None:
        """Initialize the service.

        Args:
            model: LLM model name override.
        """
        self.release_repo = ReleaseRepository()
        self.report_repo = ReportRepository()
        self.llm = LLMProvider(model=model)
        self.settings = get_settings()

    async def generate_weekly_digest(self, product_ids: list[str]) -> DigestReport:
        """Generate a weekly digest covering the specified products.

        Args:
            product_ids: List of product identifiers to include.

        Returns:
            Generated DigestReport.
        """
        with correlation_context():
            return await self._generate_digest(product_ids, "weekly", days=7)

    async def generate_monthly_digest(self, product_ids: list[str]) -> DigestReport:
        """Generate a monthly digest covering the specified products.

        Args:
            product_ids: List of product identifiers to include.

        Returns:
            Generated DigestReport.
        """
        with correlation_context():
            return await self._generate_digest(product_ids, "monthly", days=30)

    async def _generate_digest(
        self,
        product_ids: list[str],
        window_name: str,
        days: int,
    ) -> DigestReport:
        """Internal implementation for digest generation.

        Args:
            product_ids: List of product identifiers to include.
            window_name: Human-readable window label ('weekly' or 'monthly').
            days: Number of days to look back for recent releases.

        Returns:
            Generated DigestReport.
        """
        from pia.services.product_service import ProductService

        context = get_context_dict()
        product_svc = ProductService()

        cutoff = now_utc() - timedelta(days=days)

        logger.info(
            "generating digest",
            window=window_name,
            product_count=len(product_ids),
            **context,
        )

        # Gather per-product data
        products_info: list[dict] = []
        for pid in product_ids:
            product = product_svc.get_product(pid)
            if not product:
                logger.warning("product not found for digest", product_id=pid, **context)
                continue

            releases = self.release_repo.list_by_product(pid, limit=10)
            recent = [r for r in releases if r.discovered_at and r.discovered_at > cutoff]
            if not recent:
                logger.info(
                    "no recent releases for product",
                    product_id=pid,
                    days=days,
                    **context,
                )
                continue

            # Get the most recent available report
            latest = recent[0]
            reports = self.report_repo.list_by_release(latest.id)
            summary = reports[0].content_md[:2000] if reports else "No analysis available."

            products_info.append({
                "product": product,
                "releases": recent,
                "latest_summary": summary,
            })

        if not products_info:
            logger.warning(
                "no products with recent releases for digest",
                **context,
            )
            content_md = f"# {window_name.capitalize()} Digest\n\nNo recent releases found in the specified time window."
        else:
            content_md, _ = await self.llm.generate_digest(products_info, window_name)

        digest = DigestReport(
            id=str(uuid.uuid4()),
            product_ids=product_ids,
            time_window=window_name,
            model_name=self.llm.model,
            prompt_version=PROMPT_VERSION,
            content_md=content_md,
            content_hash=hash_content(content_md),
            generated_at=now_utc(),
        )

        # Save to file
        report_path = (
            self.settings.reports_dir / f"digest_{window_name}_{digest.id[:8]}.md"
        )
        report_path.write_text(content_md, encoding="utf-8")
        logger.info("digest saved", path=str(report_path), **context)

        return digest
