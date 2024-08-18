#!/usr/bin/env python3
"""Initialize liminalis_db and optionally migrate radar data into PostgreSQL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.db.postgres import ensure_database, init_schema, upsert_radar_items
from backend.services.radar_service import load_py_radar_snapshot, storage_item_to_api_dict
from backend.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-db", action="store_true", help="Create liminalis_db if it does not exist")
    parser.add_argument("--migrate-radar", action="store_true", help="Import radar rows into PostgreSQL")
    parser.add_argument(
        "--source",
        choices=("duckdb", "snapshot"),
        default="duckdb",
        help="Radar migration source",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.postgres_configured:
        print("PostgreSQL is not configured. Add pgsql_host/user/password to ~/.env.", file=sys.stderr)
        return 2

    if args.create_db:
        created = ensure_database(settings)
        print(f"{'Created' if created else 'Found'} PostgreSQL database {settings.pgsql_database}")

    init_schema(settings)
    print(f"Initialized PostgreSQL schema in database {settings.pgsql_database}")

    if args.migrate_radar:
        items = _load_radar_items(settings, args.source)
        inserted = upsert_radar_items(settings, items)
        print(f"Upserted {inserted} radar items from {args.source}")

    return 0


def _load_radar_items(settings, source: str) -> list[dict]:
    if source == "snapshot":
        snapshot_path = settings.xlab_root / "liminalis" / "src" / "data" / "pyRadarFeed.js"
        return load_py_radar_snapshot(snapshot_path).get("items") or []

    from backend.radar.storage import DuckDBStore

    store = DuckDBStore(data_dir=Path(settings.radar_data_dir), db_name=settings.radar_db_name)
    try:
        return [storage_item_to_api_dict(item) for item in store.query_by_sync_batch(limit=100000, offset=0)]
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
