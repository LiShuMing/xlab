"""Incremental data export functionality for Mac (local) side.

Exports incremental data from DuckDB to Parquet format for OSS upload.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from dbradar.storage import DuckDBStore
from dbradar.sync.models import SyncMetadata, SyncStatus, compute_file_checksum

logger = logging.getLogger(__name__)

# Default location for sync status tracking
DEFAULT_SYNC_STATUS_PATH = Path("data/sync_status.json")


def get_last_sync_time(status_path: Optional[Path] = None) -> Optional[datetime]:
    """Get the last successful sync time.

    Args:
        status_path: Path to sync status file (default: data/sync_status.json)

    Returns:
        Last sync datetime, or None if no previous sync
    """
    if status_path is None:
        status_path = DEFAULT_SYNC_STATUS_PATH

    status = SyncStatus.load(status_path)
    return status.last_sync_at


def export_incremental(
    store: DuckDBStore,
    since: Optional[datetime] = None,
    output_dir: Optional[Path] = None,
    status_path: Optional[Path] = None,
) -> tuple[Path, SyncMetadata]:
    """Export incremental data from DuckDB to Parquet file.

    Args:
        store: DuckDB storage instance
        since: Export data fetched after this time (None = export all)
        output_dir: Directory for output files (default: data/sync/)
        status_path: Path to sync status file for tracking last sync

    Returns:
        Tuple of (parquet_path, metadata)
    """
    if output_dir is None:
        output_dir = Path("data/sync")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine the since time
    if since is None and status_path is not False:
        # Try to get from status file
        since = get_last_sync_time(status_path if status_path else DEFAULT_SYNC_STATUS_PATH)
        if since:
            logger.info(f"Exporting incremental data since {since.isoformat()}")
        else:
            logger.info("No previous sync found, exporting all data")

    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_path = output_dir / f"dbradar_sync_{timestamp}.parquet"
    metadata_path = output_dir / f"dbradar_sync_{timestamp}.json"

    # Query incremental data using DuckDB's native Parquet export
    conn = store._get_conn()

    # Build the query based on since time
    if since:
        query = """
            SELECT * FROM items
            WHERE fetched_at > ?
            ORDER BY fetched_at ASC
        """
        params = [since]
    else:
        query = "SELECT * FROM items ORDER BY fetched_at ASC"
        params = []

    # First, count the items (remove ORDER BY for count)
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    # Remove ORDER BY clause for count query
    count_query = count_query.split("ORDER BY")[0].strip()
    if params:
        count_result = conn.execute(count_query, params).fetchone()
    else:
        count_result = conn.execute(count_query).fetchone()
    item_count = count_result[0] if count_result else 0

    if item_count == 0:
        logger.info("No new data to export")
        # Return empty result
        metadata = SyncMetadata(
            file_name=parquet_path.name,
            file_size=0,
            item_count=0,
            since=since,
        )
        return parquet_path, metadata

    logger.info(f"Exporting {item_count} items to {parquet_path}")

    # Export to Parquet using DuckDB's native COPY command
    # Create a temporary view for the incremental data
    if params:
        conn.execute("CREATE OR REPLACE TEMPORARY VIEW incremental_items AS " + query, params)
    else:
        conn.execute("CREATE OR REPLACE TEMPORARY VIEW incremental_items AS " + query)

    # Copy to Parquet with Snappy compression
    conn.execute(f"""
        COPY (SELECT * FROM incremental_items)
        TO '{parquet_path}'
        (FORMAT PARQUET, COMPRESSION 'SNAPPY')
    """)

    # Get date range of exported data
    date_range_query = """
        SELECT MIN(published_date), MAX(published_date)
        FROM incremental_items
    """
    date_range_result = conn.execute(date_range_query).fetchone()
    date_range = []
    if date_range_result and date_range_result[0]:
        date_range = [str(date_range_result[0]), str(date_range_result[1])]

    # Clean up temporary view
    conn.execute("DROP VIEW IF EXISTS incremental_items")

    # Compute checksum
    file_size = parquet_path.stat().st_size
    checksum = compute_file_checksum(parquet_path)

    # Create metadata
    metadata = SyncMetadata(
        version="1.0",
        file_name=parquet_path.name,
        file_size=file_size,
        item_count=item_count,
        date_range=date_range,
        checksum=checksum,
        since=since,
    )

    # Save metadata
    metadata.save(metadata_path)
    logger.info(f"Exported {item_count} items ({file_size} bytes) to {parquet_path}")
    logger.info(f"Metadata saved to {metadata_path}")

    return parquet_path, metadata


def update_sync_status(
    metadata: SyncMetadata,
    status_path: Optional[Path] = None,
) -> None:
    """Update the sync status after successful export.

    Args:
        metadata: Metadata of the exported sync file
        status_path: Path to sync status file
    """
    if status_path is None:
        status_path = DEFAULT_SYNC_STATUS_PATH

    status_path.parent.mkdir(parents=True, exist_ok=True)

    status = SyncStatus.load(status_path)
    status.last_sync_at = metadata.exported_at
    status.last_sync_file = metadata.file_name
    status.total_synced_items += metadata.item_count
    status.sync_count += 1

    status.save(status_path)
    logger.info(f"Updated sync status: {status.sync_count} total syncs, last at {status.last_sync_at}")
