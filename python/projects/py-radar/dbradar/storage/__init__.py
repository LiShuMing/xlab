"""Storage module for DB Radar.

Provides pluggable storage backends for news items.
"""

from dbradar.storage.base import ItemStore, StorageItem
from dbradar.storage.duckdb_store import DuckDBStore

__all__ = ["ItemStore", "StorageItem", "DuckDBStore"]
