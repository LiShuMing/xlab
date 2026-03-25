"""OSS upload functionality for Mac (local) side.

Uploads incremental Parquet files to Alibaba Cloud OSS.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from dbradar.config import Config
from dbradar.sync.models import SyncMetadata

logger = logging.getLogger(__name__)

# Try to import oss2, provide helpful error if not installed
try:
    import oss2
    OSS_AVAILABLE = True
except ImportError:
    OSS_AVAILABLE = False
    logger.warning("oss2 package not installed. OSS sync will not be available.")
    logger.warning("Install with: pip install oss2")


class OSSClient:
    """Alibaba Cloud OSS client wrapper."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize OSS client.

        Args:
            config: Configuration object with OSS credentials

        Raises:
            ImportError: If oss2 package is not installed
            ValueError: If OSS credentials are not configured
        """
        if not OSS_AVAILABLE:
            raise ImportError(
                "oss2 package is required for OSS sync. "
                "Install with: pip install oss2"
            )

        if config is None:
            from dbradar.config import get_config
            config = get_config()

        self.config = config

        # Get credentials from config or environment
        self.access_key_id = config.oss_access_key_id
        self.access_key_secret = config.oss_access_key_secret
        self.endpoint = config.oss_endpoint
        self.bucket_name = config.oss_bucket
        self.prefix = config.oss_prefix

        if not self.access_key_id or not self.access_key_secret:
            raise ValueError(
                "OSS credentials not configured. "
                "Set DB_RADAR_OSS_ACCESS_KEY_ID and DB_RADAR_OSS_ACCESS_KEY_SECRET "
                "environment variables, or add oss_access_key_id/oss_access_key_secret to Config."
            )

        # Initialize OSS auth and bucket
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

        logger.debug(f"OSS client initialized for bucket {self.bucket_name} at {self.endpoint}")

    def upload(
        self,
        local_path: Path,
        remote_key: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> str:
        """Upload a file to OSS.

        Args:
            local_path: Path to local file
            remote_key: Remote object key (default: auto-generated from filename)
            progress_callback: Optional callback for upload progress

        Returns:
            OSS URL of the uploaded file
        """
        if remote_key is None:
            remote_key = f"{self.prefix}{local_path.name}"

        logger.info(f"Uploading {local_path} to oss://{self.bucket_name}/{remote_key}")

        # Upload with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.bucket.put_object_from_file(
                    remote_key,
                    str(local_path),
                    progress_callback=progress_callback,
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Upload attempt {attempt + 1} failed: {e}, retrying...")
                else:
                    raise

        url = f"https://{self.bucket_name}.{self.endpoint}/{remote_key}"
        logger.info(f"Upload complete: {url}")
        return url

    def download(self, remote_key: str, local_path: Path) -> bool:
        """Download a file from OSS.

        Args:
            remote_key: Remote object key
            local_path: Path to save the file locally

        Returns:
            True if successful, False otherwise
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading oss://{self.bucket_name}/{remote_key} to {local_path}")

        try:
            self.bucket.get_object_to_file(remote_key, str(local_path))
            logger.info(f"Download complete: {local_path}")
            return True
        except oss2.exceptions.NoSuchKey:
            logger.error(f"Object not found: {remote_key}")
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def list_objects(self, prefix: Optional[str] = None) -> List[dict]:
        """List objects in the bucket.

        Args:
            prefix: Optional prefix filter

        Returns:
            List of object metadata dictionaries
        """
        if prefix is None:
            prefix = self.prefix

        objects = []
        marker = ""

        while True:
            result = self.bucket.list_objects(prefix, marker=marker)
            for obj in result.object_list:
                objects.append({
                    "key": obj.key,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                })

            if not result.is_truncated:
                break
            marker = result.next_marker

        return objects

    def object_exists(self, remote_key: str) -> bool:
        """Check if an object exists in OSS.

        Args:
            remote_key: Remote object key

        Returns:
            True if object exists
        """
        return self.bucket.object_exists(remote_key)

    def delete(self, remote_key: str) -> bool:
        """Delete an object from OSS.

        Args:
            remote_key: Remote object key

        Returns:
            True if successful
        """
        try:
            self.bucket.delete_object(remote_key)
            logger.info(f"Deleted oss://{self.bucket_name}/{remote_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {remote_key}: {e}")
            return False


def upload_sync_file(
    parquet_path: Path,
    metadata: SyncMetadata,
    config: Optional[Config] = None,
    delete_local: bool = False,
) -> tuple[str, str]:
    """Upload a sync file and its metadata to OSS.

    Args:
        parquet_path: Path to the Parquet file
        metadata: Sync metadata
        config: Configuration object
        delete_local: Whether to delete local files after successful upload

    Returns:
        Tuple of (parquet_url, metadata_url)
    """
    client = OSSClient(config)

    # Upload Parquet file
    parquet_key = f"{client.prefix}{parquet_path.name}"
    parquet_url = client.upload(parquet_path, parquet_key)

    # Upload metadata file
    metadata_path = parquet_path.with_suffix(".json")
    metadata_key = f"{client.prefix}{metadata_path.name}"
    metadata_url = client.upload(metadata_path, metadata_key)

    # Optionally delete local files
    if delete_local:
        parquet_path.unlink()
        metadata_path.unlink()
        logger.info(f"Deleted local files after upload")

    return parquet_url, metadata_url
