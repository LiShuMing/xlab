"""Analysis service: orchestrates the full fetch-normalize-analyze pipeline.

This module implements the core analysis pipeline with proper error handling,
telemetry, and context propagation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from pia.config.settings import get_settings
from pia.exceptions import AnalysisError, LLMError
from pia.llm.provider import PROMPT_VERSION, LLMProvider
from pia.models.product import Product
from pia.models.release import Release
from pia.models.report import Report
from pia.services.fetch_service import FetchService
from pia.llm.schemas import ReleaseExtraction
from pia.models.source_doc import NormalizedDoc
from pia.services.normalize_service import NormalizeService
from pia.store.repositories import ReleaseRepository, ReportRepository
from pia.telemetry import correlation_context, get_context_dict
from pia.telemetry.metrics import timed_tool_execution
from pia.utils.dates import now_utc
from pia.utils.hashing import hash_content

logger = structlog.get_logger()


class AnalysisService:
    """Orchestrates the full analysis pipeline for a single product release.

    Pipeline stages:
    1. Check report cache (skip if cache hit and not forced)
    2. Fetch raw content
    3. Normalize to markdown
    4. Stage A: structured extraction
    5. Stage B: expert analysis generation
    6. Persist report

    All stages are executed within a correlation context for proper telemetry.
    """

    def __init__(self, model: str | None = None) -> None:
        """Initialize the service.

        Args:
            model: LLM model name override. Falls back to settings.
        """
        self.fetch = FetchService()
        self.normalize = NormalizeService()
        self.llm = LLMProvider(model=model)
        self.release_repo = ReleaseRepository()
        self.report_repo = ReportRepository()
        self.settings = get_settings()

    async def analyze(
        self,
        product: Product,
        release: Release,
        force: bool = False,
    ) -> Report:
        """Run the full analysis pipeline for a single release.

        Args:
            product: Product configuration.
            release: Release to analyze.
            force: If True, bypass cache and regenerate.

        Returns:
            The generated (or cached) Report.

        Raises:
            AnalysisError: If the analysis pipeline fails.
        """
        # Use correlation context for tracing across the pipeline
        with correlation_context():
            context = get_context_dict()
            logger.info(
                "analysis pipeline started",
                product=product.id,
                version=release.version,
                force=force,
                **context,
            )

            try:
                report = await self._run_pipeline(product, release, force)
                logger.info(
                    "analysis pipeline completed",
                    product=product.id,
                    version=release.version,
                    report_id=report.id,
                    **context,
                )
                return report
            except Exception as e:
                logger.error(
                    "analysis pipeline failed",
                    product=product.id,
                    version=release.version,
                    error_type=type(e).__name__,
                    error=str(e),
                    **context,
                )
                if isinstance(e, LLMError):
                    raise AnalysisError(
                        f"Analysis failed due to LLM error: {e}",
                        details={
                            "product_id": product.id,
                            "version": release.version,
                            "error": str(e),
                        },
                    ) from e
                raise AnalysisError(
                    f"Analysis pipeline failed: {e}",
                    details={
                        "product_id": product.id,
                        "version": release.version,
                        "error": str(e),
                    },
                ) from e

    async def _run_pipeline(
        self,
        product: Product,
        release: Release,
        force: bool,
    ) -> Report:
        """Internal pipeline implementation."""
        # Determine normalized_hash for cache lookup
        normalized_hash = await self._get_normalized_hash(release)

        # Check cache
        if not force:
            cached = self.report_repo.get_cached(
                product.id,
                release.version,
                "deep_analysis",
                self.llm.model,
                PROMPT_VERSION,
                normalized_hash,
            )
            if cached:
                logger.info(
                    "cache hit",
                    product=product.id,
                    version=release.version,
                    report_id=cached.id,
                )
                return cached

        # Fetch raw content
        raw_content = await self._fetch_raw_content(product, release)

        # Normalize
        normalized = await self._normalize_content(product, release, raw_content)

        # Update release with snapshot paths
        self._update_release_paths(release, product.id, release.version)

        # Stage A: structured extraction
        extraction = await self._run_extraction(product, release, normalized)

        # Stage B: expert analysis
        content_md = await self._run_analysis(product, release, extraction, normalized)

        # Build and persist report
        report = self._create_and_save_report(
            product.id, release.id, content_md, product.id, release.version
        )

        return report

    async def _get_normalized_hash(self, release: Release) -> str:
        """Get hash of normalized content if available."""
        if (
            release.normalized_snapshot_path
            and Path(release.normalized_snapshot_path).exists()
        ):
            content = Path(release.normalized_snapshot_path).read_text(encoding="utf-8")
            return hash_content(content)
        return "unknown"

    async def _fetch_raw_content(self, product: Product, release: Release) -> str:
        """Fetch raw content from source."""
        raw_path = self.settings.raw_dir / product.id / f"{release.version}.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)

        with timed_tool_execution("fetch_url"):
            logger.info(
                "fetching raw content",
                product=product.id,
                version=release.version,
            )
            raw_content = await self.fetch.fetch_url(release.source_url, force=False)
            raw_path.write_text(raw_content, encoding="utf-8")

        return raw_content

    async def _normalize_content(
        self,
        product: Product,
        release: Release,
        raw_content: str,
    ) -> NormalizeService.NormalizedDoc:
        """Normalize raw content to markdown."""
        from pia.models.source_doc import NormalizedDoc

        with timed_tool_execution("normalize_content"):
            logger.info("normalizing content", product=product.id, version=release.version)
            if release.source_type == "github_releases":
                normalized: NormalizedDoc = self.normalize.normalize_markdown(
                    raw_content, release.source_url
                )
            else:
                normalized = self.normalize.normalize_html(raw_content, release.source_url)

            norm_path = self.settings.normalized_dir / product.id / f"{release.version}.md"
            norm_path.parent.mkdir(parents=True, exist_ok=True)
            norm_path.write_text(normalized.markdown_body, encoding="utf-8")

        return normalized

    def _update_release_paths(self, release: Release, product_id: str, version: str) -> None:
        """Update release record with snapshot paths."""
        raw_path = self.settings.raw_dir / product_id / f"{version}.html"
        norm_path = self.settings.normalized_dir / product_id / f"{version}.md"

        release.raw_snapshot_path = str(raw_path)
        release.normalized_snapshot_path = str(norm_path)
        self.release_repo.upsert(release)

    async def _run_extraction(
        self,
        product: Product,
        release: Release,
        normalized: NormalizedDoc,
    ) -> ReleaseExtraction:
        """Stage A: structured extraction."""
        from pia.llm.schemas import ReleaseExtraction

        logger.info("stage A: extraction", product=product.id, version=release.version)
        extraction: ReleaseExtraction = await self.llm.extract_release_info(
            product.name, release.version, normalized.markdown_body
        )
        return extraction

    async def _run_analysis(
        self,
        product: Product,
        release: Release,
        extraction: ReleaseExtraction,
        normalized: NormalizeService.NormalizedDoc,
    ) -> str:
        """Stage B: expert analysis generation."""
        logger.info("stage B: analysis", product=product.id, version=release.version)
        content_md, _ = await self.llm.generate_analysis(
            product, release, extraction, normalized
        )
        return content_md

    def _create_and_save_report(
        self,
        product_id: str,
        release_id: str,
        content_md: str,
        pid: str,
        version: str,
    ) -> Report:
        """Create and persist report."""
        report = Report(
            id=str(uuid.uuid4()),
            product_id=product_id,
            release_id=release_id,
            report_type="deep_analysis",
            model_name=self.llm.model,
            prompt_version=PROMPT_VERSION,
            content_md=content_md,
            content_hash=hash_content(content_md),
            generated_at=now_utc(),
        )

        # Save report to file
        report_path = self.settings.reports_dir / pid / f"{version}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content_md, encoding="utf-8")

        self.report_repo.upsert(report)
        logger.info(
            "report saved",
            product=pid,
            version=version,
            report_id=report.id,
            path=str(report_path),
        )

        return report
