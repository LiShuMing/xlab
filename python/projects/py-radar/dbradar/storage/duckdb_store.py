"""DuckDB storage implementation - unified storage for all data.

All items are stored in a single DuckDB file with proper indexing for fast queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dbradar.storage.base import ItemStore, StorageItem

logger = logging.getLogger(__name__)


class DuckDBStore(ItemStore):
    """DuckDB-based unified storage for all items.

    All data is stored in a single database file with indexes for efficient querying.
    """

    def __init__(self, data_dir: Path, db_name: str = "items.duckdb"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_dir / db_name

        # Lazy connection
        self._conn = None

    def _get_conn(self):
        """Get or create database connection."""
        if self._conn is None:
            import duckdb

            self._conn = duckdb.connect(str(self.db_path))
            self._init_schema(self._conn)
        return self._conn

    def _init_schema(self, conn) -> None:
        """Initialize database schema."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id VARCHAR PRIMARY KEY,
                url VARCHAR NOT NULL,
                title VARCHAR,
                original_title VARCHAR,
                published_date DATE,
                product VARCHAR,
                content_type VARCHAR DEFAULT 'blog',
                summary VARCHAR,
                tags VARCHAR[],
                sources VARCHAR[],
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_content VARCHAR
            )
        """)

        # Create indexes for common queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_published_date ON items(published_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_product ON items(product)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_content_type ON items(content_type)")

    def _generate_id(self, url: str) -> str:
        """Generate unique ID from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def insert(self, items: List[StorageItem]) -> int:
        """Insert items into storage."""
        if not items:
            return 0

        conn = self._get_conn()

        # Ensure all items have IDs
        for item in items:
            if not item.id:
                item.id = self._generate_id(item.url)

        # Prepare data
        data = []
        for item in items:
            data.append((
                item.id,
                item.url,
                item.title,
                item.original_title,
                item.published_date,
                item.product,
                item.content_type,
                item.summary,
                item.tags,
                item.sources,
                item.fetched_at,
                item.raw_content,
            ))

        # Use INSERT OR REPLACE for upsert
        conn.executemany("""
            INSERT OR REPLACE INTO items
            (id, url, title, original_title, published_date, product,
             content_type, summary, tags, sources, fetched_at, raw_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        conn.commit()
        logger.debug(f"Inserted {len(items)} items")
        return len(items)

    def query(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        product: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StorageItem]:
        """Query items with filters."""
        conn = self._get_conn()

        # Build WHERE clause
        conditions = []
        params = []

        if start_date:
            conditions.append("published_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("published_date <= ?")
            params.append(end_date)
        if product:
            conditions.append("product = ?")
            params.append(product)
        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)
        if tags:
            # DuckDB array contains check
            conditions.append("list_has_any(tags, ?)")
            params.append(tags)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = conn.execute(f"""
            SELECT * FROM items
            WHERE {where_clause}
            ORDER BY published_date DESC, fetched_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset]).fetchall()

        return [self._row_to_item(row) for row in rows]

    def get_by_date(self, target_date: date) -> List[StorageItem]:
        """Get all items for a specific date."""
        return self.query(start_date=target_date, end_date=target_date, limit=10000)

    def get_by_id(self, item_id: str) -> Optional[StorageItem]:
        """Get item by ID."""
        conn = self._get_conn()

        row = conn.execute(
            "SELECT * FROM items WHERE id = ?", [item_id]
        ).fetchone()

        if row:
            return self._row_to_item(row)
        return None

    def exists(self, url: str) -> bool:
        """Check if URL exists."""
        item_id = self._generate_id(url)
        return self.get_by_id(item_id) is not None

    def get_date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get min and max dates in storage."""
        conn = self._get_conn()

        row = conn.execute(
            "SELECT MIN(published_date), MAX(published_date) FROM items"
        ).fetchone()

        if row:
            return row[0], row[1]
        return None, None

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        conn = self._get_conn()

        row = conn.execute("SELECT COUNT(*) FROM items").fetchone()
        total_count = row[0] if row else 0

        min_date, max_date = self.get_date_range()

        # Get counts by content type
        type_counts = {}
        rows = conn.execute(
            "SELECT content_type, COUNT(*) FROM items GROUP BY content_type"
        ).fetchall()
        for ct, count in rows:
            type_counts[ct] = count

        return {
            "total_count": total_count,
            "date_range": (min_date, max_date),
            "by_content_type": type_counts,
            "db_path": str(self.db_path),
            "db_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0,
        }

    def _row_to_item(self, row) -> StorageItem:
        """Convert database row to StorageItem."""
        return StorageItem(
            id=row[0],
            url=row[1],
            title=row[2] or "",
            original_title=row[3] or "",
            published_date=row[4],
            product=row[5] or "",
            content_type=row[6] or "blog",
            summary=row[7] or "",
            tags=list(row[8]) if row[8] else [],
            sources=list(row[9]) if row[9] else [],
            fetched_at=row[10],
            raw_content=row[11] or "",
        )

    def get_items_without_summary(self, limit: int = 100) -> List[StorageItem]:
        """Get items that don't have a summary yet.

        Args:
            limit: Maximum number of items to return.

        Returns:
            List of StorageItem objects without summaries.
        """
        conn = self._get_conn()

        rows = conn.execute("""
            SELECT * FROM items
            WHERE summary IS NULL OR summary = ''
            ORDER BY published_date DESC, fetched_at DESC
            LIMIT ?
        """, [limit]).fetchall()

        return [self._row_to_item(row) for row in rows]

    def update_summary(self, item_id: str, summary: str) -> bool:
        """Update the summary for a specific item.

        Args:
            item_id: The unique ID of the item.
            summary: The summary text to store.

        Returns:
            True if update was successful, False otherwise.
        """
        conn = self._get_conn()

        try:
            conn.execute(
                "UPDATE items SET summary = ? WHERE id = ?",
                [summary, item_id]
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update summary for {item_id}: {e}")
            return False

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # Migration methods

    def migrate_from_json(self, json_dir: Path, dry_run: bool = False) -> Dict[str, int]:
        """Migrate existing JSON files to DuckDB.

        Args:
            json_dir: Directory containing YYYY-MM-DD.json files
            dry_run: If True, only count without inserting

        Returns:
            Statistics dict with counts
        """
        stats = {"total_files": 0, "total_items": 0, "inserted": 0, "errors": 0}

        json_files = sorted(json_dir.glob("*.json"))
        stats["total_files"] = len(json_files)

        logger.info(f"Found {len(json_files)} JSON files to migrate")

        all_items = []

        for json_file in json_files:
            # Skip non-date files
            if json_file.name in ("fetched_items.json", "index.json"):
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                items = self._convert_json_to_items(data, json_file.stem)
                all_items.extend(items)
                stats["total_items"] += len(items)
            except Exception as e:
                logger.error(f"Failed to parse {json_file}: {e}")
                stats["errors"] += 1

        logger.info(f"Parsed {stats['total_items']} items from {stats['total_files']} files")

        if not dry_run and all_items:
            # Batch insert in chunks
            chunk_size = 500
            for i in range(0, len(all_items), chunk_size):
                chunk = all_items[i:i + chunk_size]
                inserted = self.insert(chunk)
                stats["inserted"] += inserted
                logger.info(f"Migrated batch {i//chunk_size + 1}: {inserted} items")

        return stats

    def _convert_json_to_items(self, data: Dict, date_str: str) -> List[StorageItem]:
        """Convert JSON report format to StorageItems."""
        items = []

        # Parse date from filename
        try:
            report_date = date.fromisoformat(date_str)
        except ValueError:
            report_date = None

        # Process top_updates
        for update in data.get("top_updates", []):
            sources = update.get("sources", [])
            url = sources[0] if sources else ""

            if not url:
                continue

            item = StorageItem(
                id=self._generate_id(url),
                url=url,
                title=update.get("title", ""),
                original_title=update.get("original_title", update.get("title", "")),
                published_date=report_date,
                product=update.get("product", ""),
                content_type=update.get("content_type", "blog"),
                summary=self._build_summary(update),
                tags=[],  # Extracted from content
                sources=sources[1:] if len(sources) > 1 else [],
                fetched_at=datetime.fromisoformat(data.get("metadata", {}).get("generated_at", datetime.now().isoformat())),
            )
            items.append(item)

        return items

    def _build_summary(self, update: Dict) -> str:
        """Build summary from update fields."""
        parts = []

        what_changed = update.get("what_changed", [])
        if what_changed:
            parts.extend(what_changed)

        why_it_matters = update.get("why_it_matters", [])
        if why_it_matters:
            parts.extend(why_it_matters)

        evidence = update.get("evidence", [])
        if evidence:
            parts.extend(evidence[:2])

        return "；".join(parts) if parts else ""
