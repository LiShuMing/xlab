"""Analysis service: orchestrates the full fetch-normalize-analyze pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from pia.config.settings import get_settings
from pia.llm.provider import LLMProvider, PROMPT_VERSION
from pia.models.product import Product
from pia.models.release import Release
from pia.models.report import Report
from pia.services.fetch_service import FetchService
from pia.services.normalize_service import NormalizeService
from pia.store.repositories import ReleaseRepository, ReportRepository
from pia.utils.dates import now_utc
from pia.utils.hashing import hash_content, make_cache_key

log = structlog.get_logger()


class AnalysisService:
    """Orchestrates the full analysis pipeline for a single product release.

    Pipeline stages:
    1. Check report cache (skip if cache hit and not forced)
    2. Fetch raw content
    3. Normalize to markdown
    4. Stage A: structured extraction
    5. Stage B: expert analysis generation
    6. Persist report
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
        """
        # Determine normalized_hash for cache lookup
        normalized_hash = "unknown"
        if (
            release.normalized_snapshot_path
            and Path(release.normalized_snapshot_path).exists()
        ):
            content = Path(release.normalized_snapshot_path).read_text(encoding="utf-8")
            normalized_hash = hash_content(content)

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
                log.info(
                    "cache hit",
                    product=product.id,
                    version=release.version,
                    report_id=cached.id,
                )
                return cached

        # Fetch raw content
        raw_path = self.settings.raw_dir / product.id / f"{release.version}.html"
        raw_path.parent.mkdir(parents=True, exist_ok=True)

        log.info("fetching raw content", product=product.id, version=release.version)
        raw_content = await self.fetch.fetch_url(release.source_url, force=force)
        raw_path.write_text(raw_content, encoding="utf-8")

        # Normalize
        log.info("normalizing content", product=product.id, version=release.version)
        if release.source_type == "github_releases":
            normalized = self.normalize.normalize_markdown(raw_content, release.source_url)
        else:
            normalized = self.normalize.normalize_html(raw_content, release.source_url)

        norm_path = self.settings.normalized_dir / product.id / f"{release.version}.md"
        norm_path.parent.mkdir(parents=True, exist_ok=True)
        norm_path.write_text(normalized.markdown_body, encoding="utf-8")

        # Update release with snapshot paths
        release.raw_snapshot_path = str(raw_path)
        release.normalized_snapshot_path = str(norm_path)
        self.release_repo.upsert(release)

        # Stage A: structured extraction
        log.info("stage A: extraction", product=product.id, version=release.version)
        extraction = await self.llm.extract_release_info(
            product.name, release.version, normalized.markdown_body
        )

        # Stage B: expert analysis
        log.info("stage B: analysis", product=product.id, version=release.version)
        content_md, prompt_version = await self.llm.generate_analysis(
            product, release, extraction, normalized
        )

        # Build and persist report
        report = Report(
            id=str(uuid.uuid4()),
            product_id=product.id,
            release_id=release.id,
            report_type="deep_analysis",
            model_name=self.llm.model,
            prompt_version=prompt_version,
            content_md=content_md,
            content_hash=hash_content(content_md),
            generated_at=now_utc(),
        )

        # Save report to file
        report_path = self.settings.reports_dir / product.id / f"{release.version}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content_md, encoding="utf-8")

        self.report_repo.upsert(report)
        log.info(
            "report saved",
            product=product.id,
            version=release.version,
            report_id=report.id,
            path=str(report_path),
        )
        return report
