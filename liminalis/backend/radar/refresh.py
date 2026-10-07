"""Background refresh pipeline for recent Radar feed items."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from backend._shared.serializers import domain_from_url, utc_now
from backend._shared.storage import business_uow
from backend.radar.extractor import ExtractedItem, Extractor
from backend.radar.feeds import parse_feeds_file
from backend.radar.fetcher import Fetcher
from backend.radar.identity import deduplicate_radar_items, radar_item_id
from backend.radar.normalize import Normalizer
from backend.radar.ranker import rank_items
from backend.radar.service import upsert_radar_items_bulk
from backend.settings import Settings

logger = logging.getLogger(__name__)

_refresh_status: dict[str, Any] = {"state": "idle"}


def get_radar_refresh_status() -> dict[str, Any]:
    return dict(_refresh_status)


def schedule_startup_radar_refresh(settings: Settings) -> asyncio.Task[None] | None:
    """Schedule a non-blocking refresh for application startup."""
    if not settings.radar_refresh_on_startup:
        _set_status("disabled")
        return None

    artifact_path = radar_artifact_path(settings)
    if _artifact_is_fresh(artifact_path, settings.radar_refresh_min_interval_minutes):
        _set_status("throttled", artifact=str(artifact_path))
        return None

    _set_status("scheduled", feedsFile=str(settings.radar_feeds_file))
    return asyncio.create_task(_run_delayed_refresh(settings), name="radar-startup-refresh")


async def stop_startup_radar_refresh(task: asyncio.Task[None] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def refresh_latest_radar_news(settings: Settings) -> dict[str, Any]:
    """Fetch recent feeds, persist to PG when available, and update the local artifact."""
    started_at = utc_now()
    _set_status("running", startedAt=started_at.isoformat(), feedsFile=str(settings.radar_feeds_file))

    items, feed_count, success_count = await asyncio.to_thread(_collect_latest_news, settings)
    artifact_path = radar_artifact_path(settings)
    _write_artifact(artifact_path, items, started_at)

    persisted = 0
    if settings.postgres_configured and items:
        async with business_uow() as session:
            persisted = await upsert_radar_items_bulk(session, items)

    result = {
        "state": "completed",
        "feeds": feed_count,
        "successfulFeeds": success_count,
        "items": len(items),
        "persisted": persisted,
        "storage": "postgres+artifact" if settings.postgres_configured else "local-artifact",
        "artifact": str(artifact_path),
        "completedAt": utc_now().isoformat(),
    }
    _refresh_status.clear()
    _refresh_status.update(result)
    logger.info("Radar startup refresh completed: %s", result)
    return result


def radar_artifact_path(settings: Settings) -> Path:
    return settings.data_dir / "artifacts" / "radar" / "latest.json"


def load_radar_artifact(settings: Settings) -> dict[str, Any]:
    path = radar_artifact_path(settings)
    if not path.exists():
        return {"items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    return payload if isinstance(payload, dict) else {"items": []}


async def _run_delayed_refresh(settings: Settings) -> None:
    try:
        if settings.radar_refresh_startup_delay:
            await asyncio.sleep(settings.radar_refresh_startup_delay)
        await asyncio.wait_for(
            refresh_latest_radar_news(settings),
            timeout=settings.radar_refresh_timeout,
        )
    except asyncio.CancelledError:
        _set_status("cancelled")
        raise
    except Exception as exc:
        logger.exception("Radar startup refresh failed")
        _set_status("failed", error=exc.__class__.__name__, message=str(exc))


def _collect_latest_news(settings: Settings) -> tuple[list[dict[str, Any]], int, int]:
    feeds = parse_feeds_file(settings.radar_feeds_file)
    if not feeds:
        raise RuntimeError(f"No Radar feeds configured in {settings.radar_feeds_file}")

    results = Fetcher(timeout=min(settings.http_timeout, 30)).fetch_feeds(feeds, use_cache=False)
    success_count = sum(1 for result in results if result.status_code and result.status_code < 400)
    if success_count == 0:
        raise RuntimeError("All configured Radar feeds failed")
    extracted = Extractor().extract_all(results)
    normalizer = Normalizer()
    recent = _filter_recent_extracted_items(extracted, normalizer, settings.radar_days)
    normalized = normalizer.normalize(recent)
    ranked = rank_items(normalized, days=settings.radar_days, max_items=settings.radar_max_items)
    items = deduplicate_radar_items([_ranked_item_to_data(item) for item in ranked])
    return items, len(feeds), success_count


def _filter_recent_extracted_items(
    items: list[ExtractedItem],
    normalizer: Normalizer,
    max_days: int,
    max_undated_per_product: int = 3,
) -> list[ExtractedItem]:
    """Bound the expensive similarity pass to recent, relevant feed entries."""
    cutoff = utc_now() - timedelta(days=max_days)
    filtered: list[ExtractedItem] = []
    undated_counts: dict[str, int] = {}

    for item in items:
        published_at = normalizer.parse_date(item.published_at)
        if published_at is not None:
            if published_at >= cutoff:
                filtered.append(item)
            continue

        if item.confidence <= 0.7:
            continue
        product_key = item.product.casefold()
        if undated_counts.get(product_key, 0) >= max_undated_per_product:
            continue
        undated_counts[product_key] = undated_counts.get(product_key, 0) + 1
        filtered.append(item)

    return filtered


def _ranked_item_to_data(ranked_item: Any) -> dict[str, Any]:
    item = ranked_item.item
    summary = " ".join(item.content.split())[:1200]
    return {
        "id": radar_item_id(item.url),
        "url": item.url,
        "site": domain_from_url(item.url),
        "title": item.title,
        "originalTitle": item.title,
        "publishedDate": item.published_at[:10] if item.published_at else None,
        "product": item.product,
        "contentType": item.content_type,
        "summary": summary,
        "tags": [],
        "sources": item.sources,
        "fetchedAt": utc_now(),
        "rawContent": item.content,
        "syncBatch": date.today(),
    }


def _write_artifact(path: Path, items: list[dict[str, Any]], generated_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "radar-startup-refresh",
        "generatedAt": generated_at.isoformat(),
        "latestSyncBatch": generated_at.date().isoformat(),
        "totalItems": len(items),
        "items": [
            {key: value for key, value in item.items() if key not in {"rawContent", "raw_content"}}
            for item in items
        ],
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _artifact_is_fresh(path: Path, min_interval_minutes: int) -> bool:
    if min_interval_minutes <= 0 or not path.exists():
        return False
    age_seconds = datetime.now().timestamp() - path.stat().st_mtime
    return age_seconds < min_interval_minutes * 60


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _set_status(state: str, **details: Any) -> None:
    _refresh_status.clear()
    _refresh_status.update({"state": state, **details})
