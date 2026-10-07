#!/usr/bin/env python3
"""Export Radar business-database items into a Vite-consumable JSON feed."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path

from backend._shared.storage import business_uow
from backend.radar import service as radar_service
from backend.radar.identity import deduplicate_radar_items
from backend.settings import get_settings

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "src" / "data" / "pyRadarFeed.js"


def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


async def export_feed(output: Path, limit: int) -> int:
    settings = get_settings()
    async with business_uow() as session:
        result = await radar_service.query_radar_items(
            session,
            page=1,
            per_page=max(1, limit),
            content_type="all",
            product="all",
            query="",
        )

    result = result or {"items": [], "products": [], "contentTypes": [], "total_items": 0}
    items = deduplicate_radar_items(result.get("items") or [])
    payload = {
        "source": "radar",
        "sourcePath": settings.business_database_name,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "limit": limit,
        "sourceTotalItems": result.get("total_items", 0),
        "totalItems": len(items),
        "latestSyncBatch": serialize_value(result.get("latestSyncBatch")),
        "products": result.get("products") or [],
        "contentTypes": result.get("contentTypes") or [],
        "items": items,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    content = "const pyRadarFeed = "
    content += json.dumps(payload, ensure_ascii=False, indent=2)
    content += ";\n\nexport default pyRadarFeed;\n"
    output.write_text(content, encoding="utf-8")
    print(f"Exported {len(payload['items'])} of {payload['totalItems']} radar items to {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--limit", type=int, default=120, help="Maximum feed items to export")
    args = parser.parse_args()
    return asyncio.run(export_feed(args.output, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
