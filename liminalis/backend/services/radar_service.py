"""Read-only radar feed service for the unified backend."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.radar.service import query_radar_items as _query_pg
from backend.settings import Settings


@dataclass(frozen=True)
class RadarQuery:
    page: int = 1
    per_page: int = 80
    content_type: str = "all"
    product: str = "all"
    query: str = ""


async def read_radar_items(
    session: AsyncSession, settings: Settings, radar_query: RadarQuery
) -> dict[str, Any]:
    page = max(radar_query.page, 1)
    per_page = min(max(radar_query.per_page, 1), 100)
    content_type = radar_query.content_type or "all"
    product = radar_query.product or "all"
    query = radar_query.query.strip().lower()

    try:
        result = await _query_pg(
            session,
            page=page,
            per_page=per_page,
            content_type=content_type,
            product=product,
            query=query,
        )
        if result:
            return result
    except Exception:
        if settings.storage_backend == "postgres":
            raise

    return read_snapshot_radar_items(settings, radar_query)


def read_snapshot_radar_items(settings: Settings, radar_query: RadarQuery) -> dict[str, Any]:
    snapshot_path = settings.xlab_root / "liminalis" / "src" / "data" / "pyRadarFeed.js"
    payload = load_py_radar_snapshot(snapshot_path)
    items = payload.get("items") or []

    page = max(radar_query.page, 1)
    per_page = min(max(radar_query.per_page, 1), 100)
    content_type = radar_query.content_type or "all"
    product = radar_query.product or "all"
    query = radar_query.query.strip().lower()

    def matches(item: dict[str, Any]) -> bool:
        searchable = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("originalTitle") or ""),
                str(item.get("product") or ""),
                str(item.get("contentType") or ""),
                str(item.get("summary") or ""),
                " ".join(item.get("tags") or []),
            ]
        ).lower()
        return (
            (content_type in {"", "all"} or item.get("contentType") == content_type)
            and (product in {"", "all"} or item.get("product") == product)
            and (not query or query in searchable)
        )

    filtered = [item for item in items if matches(item)]
    total_items = len(filtered)
    total_pages = (total_items + per_page - 1) // per_page if total_items else 0
    offset = (page - 1) * per_page

    return {
        "items": filtered[offset : offset + per_page],
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "products": payload.get("products") or [],
        "contentTypes": payload.get("contentTypes") or [],
        "latestSyncBatch": payload.get("latestSyncBatch"),
    }


def extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "") or ""
    except Exception:
        return ""


def storage_item_to_api_dict(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "originalTitle": item.original_title or item.title,
        "url": item.url,
        "site": extract_domain(item.url),
        "product": item.product,
        "summary": item.summary,
        "tags": item.tags,
        "sources": item.sources,
        "publishedDate": item.published_date.isoformat() if item.published_date else None,
        "contentType": item.content_type,
        "fetchedAt": item.fetched_at.isoformat() if item.fetched_at else None,
        "syncBatch": item.sync_batch.isoformat() if item.sync_batch else None,
    }


def load_py_radar_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": [], "products": [], "contentTypes": []}

    content = path.read_text(encoding="utf-8")
    match = re.search(
        r"const\s+pyRadarFeed\s*=\s*(\{.*\})\s*;\s*export\s+default\s+pyRadarFeed", content, re.S
    )
    if not match:
        return {"items": [], "products": [], "contentTypes": []}
    return json.loads(match.group(1))
