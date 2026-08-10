#!/usr/bin/env python3
"""Initialize the business database and optionally import Radar snapshot data."""

from __future__ import annotations

import argparse
import sys

from alembic import command
from alembic.config import Config

from backend._shared.storage import business_uow
from backend.radar import service as radar_service
from backend.services.radar_service import load_py_radar_snapshot
from backend.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrate-radar", action="store_true", help="Import Radar snapshot rows")
    parser.add_argument("--skip-migrations", action="store_true", help="Do not run Alembic upgrade")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.postgres_configured:
        print(
            "PostgreSQL is not configured. Add PSQL_URL/PSQL_USER/PSQL_PASSWORD to ~/.env.", file=sys.stderr
        )
        return 2

    if not args.skip_migrations:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        print(f"Applied Alembic migrations in {settings.business_database_name}")

    if args.migrate_radar:
        import asyncio

        inserted = asyncio.run(_import_radar_snapshot(settings))
        print(f"Upserted {inserted} radar items from snapshot")

    return 0


async def _import_radar_snapshot(settings) -> int:
    items = _load_radar_items(settings)
    async with business_uow() as session:
        return await radar_service.upsert_radar_items_bulk(session, items)


def _load_radar_items(settings) -> list[dict]:
    snapshot_path = settings.xlab_root / "liminalis" / "src" / "data" / "pyRadarFeed.js"
    return load_py_radar_snapshot(snapshot_path).get("items") or []


if __name__ == "__main__":
    raise SystemExit(main())
