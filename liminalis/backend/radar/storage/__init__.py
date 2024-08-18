"""Storage module for DB Radar.

Provides pluggable storage backends for news items.
"""

from backend.radar.storage.base import ItemStore, StorageItem
from backend.radar.storage.duckdb_store import DuckDBStore

__all__ = ["ItemStore", "StorageItem", "DuckDBStore"]
