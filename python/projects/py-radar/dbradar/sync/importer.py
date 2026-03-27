"""Incremental data import functionality for remote server side.

Imports incremental data from Parquet files into DuckDB.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from dbradar.storage import DuckDBStore
from dbradar.storage.base import StorageItem
from dbradar.sync.models import SyncMetadata, SyncStatus, compute_file_checksum

logger = logging.getLogger(__name__)

# Default location for sync status tracking on server
DEFAULT_SERVER_SYNC_STATUS_PATH = Path("data/server_sync_status.json")


def validate_checksum(parquet_path: Path, expected_checksum: str) -> bool:
    """Validate the checksum of a Parquet file.

    Args:
        parquet_path: Path to the Parquet file
        expected_checksum: Expected SHA256 checksum

    Returns:
        True if checksum matches
    """
    actual_checksum = compute_file_checksum(parquet_path)
    if actual_checksum != expected_checksum:
        logger.error(
            f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
        )
        return False
    logger.debug(f"Checksum validated: {actual_checksum}")
    return True


def import_incremental(
    store: DuckDBStore,
    parquet_path: Path,
    metadata: SyncMetadata,
    status_path: Optional[Path] = None,
) -> int:
    """Import incremental data from Parquet file into DuckDB.

    Uses INSERT OR REPLACE for conflict resolution based on item ID.

    Args:
        store: DuckDB storage instance
        parquet_path: Path to the Parquet file
        metadata: Sync metadata
        status_path: Path to server sync status file

    Returns:
        Number of items imported
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    # Validate checksum
    if not validate_checksum(parquet_path, metadata.checksum):
        raise ValueError(f"Checksum validation failed for {parquet_path}")

    conn = store._get_conn()

    # Create a temporary table from the Parquet file
    logger.info(f"Reading Parquet file: {parquet_path}")
    conn.execute(f"""
        CREATE OR REPLACE TEMPORARY TABLE incremental_data AS
        SELECT * FROM read_parquet('{parquet_path}')
    """)

    # Count items to import
    count_result = conn.execute("SELECT COUNT(*) FROM incremental_data").fetchone()
    item_count = count_result[0] if count_result else 0

    if item_count == 0:
        logger.info("No items to import")
        conn.execute("DROP TABLE IF EXISTS incremental_data")
        return 0

    logger.info(f"Importing {item_count} items with INSERT OR REPLACE")

    # Insert or replace items
    # The schema should match the items table structure
    conn.execute("""
        INSERT OR REPLACE INTO items
        SELECT
            id,
            url,
            title,
            original_title,
            published_date,
            product,
            content_type,
            summary,
            tags,
            sources,
            fetched_at,
            raw_content,
            COALESCE(sync_batch, CURRENT_DATE) as sync_batch
        FROM incremental_data
    """)

    # Clean up temporary table
    conn.execute("DROP TABLE IF EXISTS incremental_data")

    # Commit the transaction
    conn.commit()

    logger.info(f"Successfully imported {item_count} items")

    # Update server sync status
    if status_path is None:
        status_path = DEFAULT_SERVER_SYNC_STATUS_PATH

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status = SyncStatus.load(status_path)
    status.last_sync_at = metadata.exported_at
    status.last_sync_file = metadata.file_name
    status.total_synced_items += item_count
    status.sync_count += 1
    status.save(status_path)

    logger.info(f"Updated server sync status: {status.sync_count} total imports")

    return item_count


def import_from_parquet(
    store: DuckDBStore,
    parquet_path: Path,
    delete_after_import: bool = False,
) -> int:
    """Import data from a Parquet file without metadata validation.

    This is a simpler version that doesn't require metadata/checksum.
    Useful for manual imports or testing.

    Args:
        store: DuckDB storage instance
        parquet_path: Path to the Parquet file
        delete_after_import: Whether to delete the Parquet file after import

    Returns:
        Number of items imported
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

    conn = store._get_conn()

    # Create a temporary table from the Parquet file
    logger.info(f"Reading Parquet file: {parquet_path}")
    conn.execute(f"""
        CREATE OR REPLACE TEMPORARY TABLE incremental_data AS
        SELECT * FROM read_parquet('{parquet_path}')
    """)

    # Count items to import
    count_result = conn.execute("SELECT COUNT(*) FROM incremental_data").fetchone()
    item_count = count_result[0] if count_result else 0

    if item_count == 0:
        logger.info("No items to import")
        conn.execute("DROP TABLE IF EXISTS incremental_data")
        return 0

    logger.info(f"Importing {item_count} items")

    # Insert or replace items
    conn.execute("""
        INSERT OR REPLACE INTO items
        SELECT
            id,
            url,
            title,
            original_title,
            published_date,
            product,
            content_type,
            summary,
            tags,
            sources,
            fetched_at,
            raw_content,
            COALESCE(sync_batch, CURRENT_DATE) as sync_batch
        FROM incremental_data
    """)

    # Clean up temporary table
    conn.execute("DROP TABLE IF EXISTS incremental_data")
    conn.commit()

    logger.info(f"Successfully imported {item_count} items")

    # Optionally delete the file
    if delete_after_import:
        parquet_path.unlink()
        logger.info(f"Deleted {parquet_path} after import")

    return item_count


def get_import_status(status_path: Optional[Path] = None) -> SyncStatus:
    """Get the current import status on the server.

    Args:
        status_path: Path to server sync status file

    Returns:
        Current sync status
    """
    if status_path is None:
        status_path = DEFAULT_SERVER_SYNC_STATUS_PATH

    return SyncStatus.load(status_path)
