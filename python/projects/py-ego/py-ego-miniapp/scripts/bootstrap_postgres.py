#!/usr/bin/env python
"""Initialize the configured Postgres/Supabase database."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app.config import get_settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.db_init import initialize_database  # noqa: E402


def _mask_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if "@" not in parsed.netloc:
        return database_url

    _, host = parsed.netloc.rsplit("@", 1)
    return urlunsplit((parsed.scheme, f"<credentials>@{host}", parsed.path, "", ""))


async def main() -> None:
    settings = get_settings()
    print(f"Initializing database: {_mask_database_url(settings.database_url)}")
    await initialize_database(engine)
    await engine.dispose()
    print("Database is ready.")


if __name__ == "__main__":
    asyncio.run(main())
