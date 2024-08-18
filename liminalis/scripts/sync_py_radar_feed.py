#!/usr/bin/env python3
"""Export py-radar DuckDB items into a Vite-consumable JSON feed."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_DB = Path("/Users/lism/work/xlab/python/projects/py-radar/data/items.duckdb")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "src" / "data" / "pyRadarFeed.js"


def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def extract_domain(url: str) -> str:
    if not url:
        return ""
    return urlparse(url).netloc.replace("www.", "")


def normalize_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to py-radar items.duckdb")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--limit", type=int, default=120, help="Maximum feed items to export")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"py-radar database not found: {args.db}")

    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("duckdb is required to export py-radar data") from exc

    conn = duckdb.connect(str(args.db), read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT
              id,
              title,
              original_title,
              url,
              published_date,
              product,
              content_type,
              summary,
              tags,
              sources,
              fetched_at,
              sync_batch
            FROM items
            ORDER BY sync_batch DESC, published_date DESC, fetched_at DESC
            LIMIT ?
            """,
            [args.limit],
        ).fetchall()

        total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        latest_sync = conn.execute("SELECT MAX(sync_batch) FROM items").fetchone()[0]
        product_rows = conn.execute(
            """
            SELECT product, COUNT(*) AS count
            FROM items
            WHERE product IS NOT NULL AND product != ''
            GROUP BY product
            ORDER BY count DESC, product ASC
            LIMIT 24
            """
        ).fetchall()
        type_rows = conn.execute(
            """
            SELECT content_type, COUNT(*) AS count
            FROM items
            WHERE content_type IS NOT NULL AND content_type != ''
            GROUP BY content_type
            ORDER BY count DESC, content_type ASC
            """
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        (
            item_id,
            title,
            original_title,
            url,
            published_date,
            product,
            content_type,
            summary,
            tags,
            sources,
            fetched_at,
            sync_batch,
        ) = row
        items.append(
            {
                "id": item_id,
                "title": title or original_title or "Untitled",
                "originalTitle": original_title or title or "Untitled",
                "url": url or "",
                "site": extract_domain(url or ""),
                "publishedDate": serialize_value(published_date),
                "product": product or "Database",
                "contentType": content_type or "news",
                "summary": summary or "",
                "tags": normalize_list(tags),
                "sources": normalize_list(sources),
                "fetchedAt": serialize_value(fetched_at),
                "syncBatch": serialize_value(sync_batch),
            }
        )

    payload = {
        "source": "py-radar",
        "sourcePath": str(args.db),
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "limit": args.limit,
        "totalItems": total_items,
        "latestSyncBatch": serialize_value(latest_sync),
        "products": [{"name": product, "count": count} for product, count in product_rows],
        "contentTypes": [{"name": content_type, "count": count} for content_type, count in type_rows],
        "items": items,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = "const pyRadarFeed = "
    content += json.dumps(payload, ensure_ascii=False, indent=2)
    content += ";\n\nexport default pyRadarFeed;\n"
    args.output.write_text(content, encoding="utf-8")
    print(f"Exported {len(items)} of {total_items} py-radar items to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
