"""Read-only radar feed service for the unified backend."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.errors import should_fallback_after_read_error
from backend.radar.identity import deduplicate_radar_items
from backend.radar.refresh import load_radar_artifact
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
        if not should_fallback_after_read_error(settings):
            raise

    return read_snapshot_radar_items(settings, radar_query)


def read_snapshot_radar_items(settings: Settings, radar_query: RadarQuery) -> dict[str, Any]:
    snapshot_path = settings.xlab_root / "liminalis" / "src" / "data" / "pyRadarFeed.js"
    payload = merge_radar_payloads(
        load_radar_artifact(settings),
        load_py_radar_snapshot(snapshot_path),
    )
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


def load_py_radar_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": [], "products": [], "contentTypes": []}

    content = path.read_text(encoding="utf-8")
    match = re.search(
        r"const\s+pyRadarFeed\s*=\s*(\{.*\})\s*;\s*export\s+default\s+pyRadarFeed", content, re.S
    )
    if not match:
        return {"items": [], "products": [], "contentTypes": []}
    payload = json.loads(match.group(1))
    source_total = payload.get("sourceTotalItems") or payload.get("totalItems") or 0
    items = deduplicate_radar_items(payload.get("items") or [])
    payload["sourceTotalItems"] = source_total
    payload["items"] = items
    payload["totalItems"] = len(items)
    payload["products"] = _facet_counts(items, "product")
    payload["contentTypes"] = _facet_counts(items, "contentType")
    return payload


def merge_radar_payloads(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Merge refreshed and bundled items, preferring refreshed enrichment."""
    items = deduplicate_radar_items(
        [*(primary.get("items") or []), *(fallback.get("items") or [])]
    )
    latest_batches = [
        str(value)
        for value in (primary.get("latestSyncBatch"), fallback.get("latestSyncBatch"))
        if value
    ]
    return {
        **fallback,
        "sourceTotalItems": fallback.get("sourceTotalItems") or fallback.get("totalItems") or 0,
        "generatedAt": primary.get("generatedAt") or fallback.get("generatedAt"),
        "latestSyncBatch": max(latest_batches) if latest_batches else None,
        "items": items,
        "totalItems": len(items),
        "products": _facet_counts(items, "product"),
        "contentTypes": _facet_counts(items, "contentType"),
    }


def _facet_counts(items: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(item.get(field) or "") for item in items)
    return [
        {"name": name, "count": count}
        for name, count in counts.most_common()
        if name
    ]
