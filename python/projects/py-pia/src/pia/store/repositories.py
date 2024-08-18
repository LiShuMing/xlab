"""Data access repositories for products, releases, and reports."""

from __future__ import annotations

import json
import sqlite3

from pia.models.product import Product
from pia.models.release import Release
from pia.models.report import DigestReport, Report
from pia.store.db import get_connection
from pia.utils.dates import format_iso, now_utc, parse_date
from pia.utils.hashing import make_cache_key


class ProductRepository:
    """CRUD operations for Product records."""

    def upsert(self, product: Product) -> None:
        """Insert or update a product record.

        Args:
            product: Product instance to persist.
        """
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO products (id, name, category, homepage, description, config_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    homepage = excluded.homepage,
                    description = excluded.description,
                    config_path = excluded.config_path
                """,
                (
                    product.id,
                    product.name,
                    product.category,
                    product.homepage,
                    product.description,
                    product.config_path,
                    format_iso(product.created_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, product_id: str) -> Product | None:
        """Retrieve a product by its ID.

        Args:
            product_id: The product identifier.

        Returns:
            Product instance or None if not found.
        """
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_product(row)
        finally:
            conn.close()

    def list_all(self) -> list[Product]:
        """Return all products ordered by name.

        Returns:
            List of Product instances.
        """
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
            return [self._row_to_product(r) for r in rows]
        finally:
            conn.close()

    def _row_to_product(self, row: sqlite3.Row) -> Product:
        """Convert a database row to a Product model.

        Note: Sources are not stored in the products table; they come from
        the YAML config loaded at startup. This returns a Product with
        empty sources for DB-only records.
        """
        return Product(
            id=row["id"],
            name=row["name"],
            category=row["category"] or "",
            homepage=row["homepage"] or "",
            description=row["description"] or "",
            sources=[],
            config_path=row["config_path"],
            created_at=parse_date(row["created_at"]),
        )


class ReleaseRepository:
    """CRUD operations for Release records."""

    def upsert(self, release: Release) -> None:
        """Insert or update a release record.

        Uses (product_id, version) as the unique constraint.

        Args:
            release: Release instance to persist.
        """
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO releases (
                    id, product_id, version, title, published_at,
                    source_url, source_type, source_hash,
                    raw_snapshot_path, normalized_snapshot_path, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, version) DO UPDATE SET
                    title = excluded.title,
                    published_at = excluded.published_at,
                    source_url = excluded.source_url,
                    source_type = excluded.source_type,
                    source_hash = excluded.source_hash,
                    raw_snapshot_path = COALESCE(excluded.raw_snapshot_path, releases.raw_snapshot_path),
                    normalized_snapshot_path = COALESCE(excluded.normalized_snapshot_path, releases.normalized_snapshot_path)
                """,
                (
                    release.id,
                    release.product_id,
                    release.version,
                    release.title,
                    format_iso(release.published_at),
                    release.source_url,
                    release.source_type,
                    release.source_hash,
                    release.raw_snapshot_path,
                    release.normalized_snapshot_path,
                    format_iso(release.discovered_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, release_id: str) -> Release | None:
        """Retrieve a release by its ID.

        Args:
            release_id: The release identifier.

        Returns:
            Release instance or None if not found.
        """
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM releases WHERE id = ?", (release_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_release(row)
        finally:
            conn.close()

    def get_latest_by_product(self, product_id: str) -> Release | None:
        """Return the latest release for a product by version sort order.

        Args:
            product_id: Product identifier.

        Returns:
            The newest Release or None if no releases exist.
        """
        releases = self.list_by_product(product_id, limit=50)
        if not releases:
            return None
        from pia.utils.versioning import version_sort_key

        return sorted(releases, key=lambda r: version_sort_key(r.version), reverse=True)[0]

    def list_by_product(self, product_id: str, limit: int = 20) -> list[Release]:
        """Return releases for a product, ordered by discovered_at descending.

        Args:
            product_id: Product identifier.
            limit: Maximum number of releases to return.

        Returns:
            List of Release instances.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM releases
                WHERE product_id = ?
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (product_id, limit),
            ).fetchall()
            releases = [self._row_to_release(r) for r in rows]
            # Re-sort by semantic version for consistent ordering
            from pia.utils.versioning import version_sort_key

            return sorted(releases, key=lambda r: version_sort_key(r.version), reverse=True)
        finally:
            conn.close()

    def get_by_product_version(self, product_id: str, version: str) -> Release | None:
        """Retrieve a specific release by product ID and version.

        Args:
            product_id: Product identifier.
            version: Version string (normalized or raw).

        Returns:
            Release instance or None if not found.
        """
        from pia.utils.versioning import normalize_version

        normalized = normalize_version(version)

        conn = get_connection()
        try:
            # Try exact match first, then normalized
            row = conn.execute(
                "SELECT * FROM releases WHERE product_id = ? AND version = ?",
                (product_id, version),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM releases WHERE product_id = ? AND version = ?",
                    (product_id, normalized),
                ).fetchone()
            if row is None:
                return None
            return self._row_to_release(row)
        finally:
            conn.close()

    def _row_to_release(self, row: sqlite3.Row) -> Release:
        return Release(
            id=row["id"],
            product_id=row["product_id"],
            version=row["version"],
            title=row["title"] or "",
            published_at=parse_date(row["published_at"]),
            source_url=row["source_url"] or "",
            source_type=row["source_type"] or "",
            source_hash=row["source_hash"] or "",
            raw_snapshot_path=row["raw_snapshot_path"],
            normalized_snapshot_path=row["normalized_snapshot_path"],
            discovered_at=parse_date(row["discovered_at"]) or now_utc(),
        )


class ReportRepository:
    """CRUD operations for Report records."""

    def upsert(self, report: Report) -> None:
        """Insert or update a report record.

        Args:
            report: Report instance to persist.
        """
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO reports (
                    id, product_id, release_id, report_type,
                    model_name, prompt_version, content_md, content_hash, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content_md = excluded.content_md,
                    content_hash = excluded.content_hash,
                    generated_at = excluded.generated_at
                """,
                (
                    report.id,
                    report.product_id,
                    report.release_id,
                    report.report_type,
                    report.model_name,
                    report.prompt_version,
                    report.content_md,
                    report.content_hash,
                    format_iso(report.generated_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_cached(
        self,
        product_id: str,
        version: str,
        report_type: str,
        model_name: str,
        prompt_version: str,
        normalized_hash: str,
    ) -> Report | None:
        """Look up a cached report by the full cache key tuple.

        Args:
            product_id: Product identifier.
            version: Release version string.
            report_type: Report type (e.g. 'deep_analysis').
            model_name: LLM model name.
            prompt_version: Prompt template version.
            normalized_hash: Hash of normalized source content.

        Returns:
            Cached Report or None if no matching report exists.
        """
        # Compute cache key for verification
        _ = make_cache_key(
            product_id, version, report_type, model_name, prompt_version, normalized_hash
        )
        conn = get_connection()
        try:
            # Look for reports with matching product/type/model/prompt
            rows = conn.execute(
                """
                SELECT r.* FROM reports r
                JOIN releases rel ON r.release_id = rel.id
                WHERE r.product_id = ?
                  AND rel.version = ?
                  AND r.report_type = ?
                  AND r.model_name = ?
                  AND r.prompt_version = ?
                ORDER BY r.generated_at DESC
                LIMIT 1
                """,
                (product_id, version, report_type, model_name, prompt_version),
            ).fetchall()

            if rows:
                return self._row_to_report(rows[0])
            return None
        finally:
            conn.close()

    def list_by_release(self, release_id: str) -> list[Report]:
        """Return all reports for a specific release.

        Args:
            release_id: Release identifier.

        Returns:
            List of Report instances ordered by generated_at descending.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM reports
                WHERE release_id = ?
                ORDER BY generated_at DESC
                """,
                (release_id,),
            ).fetchall()
            return [self._row_to_report(r) for r in rows]
        finally:
            conn.close()

    def list_by_product(self, product_id: str, limit: int = 20) -> list[Report]:
        """Return reports for a product ordered by generated_at descending.

        Args:
            product_id: Product identifier.
            limit: Maximum number of reports to return.

        Returns:
            List of Report instances.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM reports
                WHERE product_id = ?
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (product_id, limit),
            ).fetchall()
            return [self._row_to_report(r) for r in rows]
        finally:
            conn.close()

    def _row_to_report(self, row: sqlite3.Row) -> Report:
        return Report(
            id=row["id"],
            product_id=row["product_id"],
            release_id=row["release_id"],
            report_type=row["report_type"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            content_md=row["content_md"],
            content_hash=row["content_hash"],
            generated_at=parse_date(row["generated_at"]) or now_utc(),
        )


class DigestReportRepository:
    """CRUD operations for DigestReport records."""

    def upsert(self, digest: DigestReport) -> None:
        """Insert or update a digest report record.

        Args:
            digest: DigestReport instance to persist.
        """
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO digest_reports (
                    id, product_ids, time_window, model_name,
                    prompt_version, content_md, content_hash, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content_md = excluded.content_md,
                    content_hash = excluded.content_hash,
                    generated_at = excluded.generated_at
                """,
                (
                    digest.id,
                    json.dumps(digest.product_ids),
                    digest.time_window,
                    digest.model_name,
                    digest.prompt_version,
                    digest.content_md,
                    digest.content_hash,
                    format_iso(digest.generated_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_recent(self, limit: int = 10) -> list[DigestReport]:
        """Return recent digest reports.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of DigestReport instances ordered by generated_at descending.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM digest_reports
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_digest(r) for r in rows]
        finally:
            conn.close()

    def _row_to_digest(self, row: sqlite3.Row) -> DigestReport:
        return DigestReport(
            id=row["id"],
            product_ids=json.loads(row["product_ids"]),
            time_window=row["time_window"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            content_md=row["content_md"],
            content_hash=row["content_hash"],
            generated_at=parse_date(row["generated_at"]) or now_utc(),
        )
