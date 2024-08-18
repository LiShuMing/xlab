"""OSS download functionality for remote server side.

Downloads incremental Parquet files from Alibaba Cloud OSS.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from backend.radar.config import Config
from backend.radar.sync.models import SyncMetadata
from backend.radar.sync.uploader import OSSClient

logger = logging.getLogger(__name__)


def list_sync_files(
    config: Config | None = None,
    prefix: str | None = None,
) -> list[SyncMetadata]:
    """List all sync files available in OSS.

    Args:
        config: Configuration object
        prefix: Optional prefix override

    Returns:
        List of SyncMetadata objects sorted by export time (newest first)
    """
    client = OSSClient(config)

    if prefix is None:
        prefix = client.prefix

    objects = client.list_objects(prefix)

    # Filter to only metadata files (JSON)
    metadata_files = [obj for obj in objects if obj["key"].endswith(".json")]

    sync_metadata_list = []
    for obj in metadata_files:
        try:
            # Download metadata file temporarily to parse it
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
                temp_path = Path(f.name)

            if client.download(obj["key"], temp_path):
                metadata = SyncMetadata.load(temp_path)
                sync_metadata_list.append(metadata)
                temp_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to parse metadata for {obj['key']}: {e}")
            continue

    # Sort by export time (newest first)
    sync_metadata_list.sort(key=lambda x: x.exported_at, reverse=True)

    return sync_metadata_list


def download_sync_file(
    metadata: SyncMetadata,
    output_dir: Path,
    config: Config | None = None,
) -> Path | None:
    """Download a sync file from OSS.

    Args:
        metadata: SyncMetadata containing file information
        output_dir: Directory to save the downloaded file
        config: Configuration object

    Returns:
        Path to downloaded Parquet file, or None if failed
    """
    client = OSSClient(config)

    # Download Parquet file
    parquet_key = f"{client.prefix}{metadata.file_name}"
    parquet_path = output_dir / metadata.file_name

    if not client.download(parquet_key, parquet_path):
        return None

    # Verify checksum
    from backend.radar.sync.models import compute_file_checksum

    actual_checksum = compute_file_checksum(parquet_path)

    if actual_checksum != metadata.checksum:
        logger.error(
            f"Checksum mismatch for {metadata.file_name}: expected {metadata.checksum}, got {actual_checksum}"
        )
        parquet_path.unlink()  # Delete corrupted file
        return None

    logger.info(f"Downloaded and verified {metadata.file_name}")
    return parquet_path


def get_latest_sync_metadata(
    config: Config | None = None,
) -> SyncMetadata | None:
    """Get the latest sync metadata from OSS.

    Args:
        config: Configuration object

    Returns:
        Latest SyncMetadata, or None if no sync files found
    """
    sync_files = list_sync_files(config)
    if not sync_files:
        return None
    return sync_files[0]


def download_latest(
    output_dir: Path,
    config: Config | None = None,
    since: datetime | None = None,
) -> tuple[Path, SyncMetadata] | None:
    """Download the latest sync file if it's newer than the given time.

    Args:
        output_dir: Directory to save the downloaded file
        config: Configuration object
        since: Only download if newer than this time

    Returns:
        Tuple of (parquet_path, metadata) if downloaded, None otherwise
    """
    latest = get_latest_sync_metadata(config)
    if not latest:
        logger.info("No sync files found in OSS")
        return None

    if since and latest.exported_at <= since:
        logger.info(f"Latest sync ({latest.exported_at}) is not newer than {since}")
        return None

    parquet_path = download_sync_file(latest, output_dir, config)
    if parquet_path:
        return parquet_path, latest
    return None
