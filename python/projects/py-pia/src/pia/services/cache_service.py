"""Cache management service."""

import structlog

from pia.store.repositories import ReportRepository, ReleaseRepository
from pia.models.report import Report

log = structlog.get_logger()


class CacheService:
    """Provides cache inspection and management operations for reports."""

    def __init__(self) -> None:
        self.report_repo = ReportRepository()
        self.release_repo = ReleaseRepository()

    def list_cached_reports(self, product_id: str | None = None) -> list[Report]:
        """List all cached reports, optionally filtered by product.

        Args:
            product_id: If provided, only return reports for this product.

        Returns:
            List of Report instances.
        """
        if product_id:
            return self.report_repo.list_by_product(product_id, limit=100)
        # Without product filter, fetch reports for each product via release
        conn = __import__("pia.store.db", fromlist=["get_connection"]).get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY generated_at DESC LIMIT 100"
            ).fetchall()
            from pia.utils.dates import parse_date, now_utc
            return [
                Report(
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
                for row in rows
            ]
        finally:
            conn.close()

    def purge_product_reports(self, product_id: str) -> int:
        """Delete all cached reports for a product.

        Args:
            product_id: Product whose reports should be purged.

        Returns:
            Number of deleted report rows.
        """
        from pia.store.db import get_connection
        conn = get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM reports WHERE product_id = ?", (product_id,)
            )
            conn.commit()
            count = cursor.rowcount
            log.info("purged reports", product_id=product_id, count=count)
            return count
        finally:
            conn.close()
