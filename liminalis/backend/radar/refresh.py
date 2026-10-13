"""Background refresh pipeline for recent Radar feed items."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from backend._shared.content import COMPONENT_KEYWORDS, extract_versions
from backend._shared.serializers import domain_from_url, utc_now
from backend._shared.storage import business_uow
from backend._shared.web_feed import is_feed_content
from backend._shared.web_fetcher import FetchTarget
from backend.radar.analysis import PROMPT_VERSION, IngestionRequest, analyze_with_llm
from backend.radar.extractor import ExtractedItem, Extractor
from backend.radar.feeds import parse_feeds_file
from backend.radar.fetcher import Fetcher
from backend.radar.identity import canonicalize_radar_url, deduplicate_radar_items, radar_item_id
from backend.radar.normalize import Normalizer
from backend.radar.ranker import rank_items
from backend.radar.service import upsert_radar_items_bulk
from backend.settings import Settings

logger = logging.getLogger(__name__)

_refresh_status: dict[str, Any] = {"state": "idle"}
_collection_metadata: dict[str, Any] = {}


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
    previous = load_radar_artifact(settings)
    artifact_items = _merge_incremental_items(
        items,
        previous.get("items") or [],
        max_days=settings.radar_days,
    )

    # Keep an unpublished source-bearing checkpoint if PG is temporarily down.
    # This prevents paid analyses being lost and is never read by the public API.
    pending_path = artifact_path.with_name("pending.json")
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(
        json.dumps(
            {
                "items": items,
                "metrics": {k: v for k, v in _collection_metadata.items() if k != "feedHealth"},
                "feedHealth": _collection_metadata.get("feedHealth", []),
            },
            ensure_ascii=False,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    persisted = 0
    try:
        if settings.postgres_configured and items:
            async with business_uow() as session:
                persisted = await upsert_radar_items_bulk(session, items)
    except Exception as exc:
        _set_status(
            "failed", reason="persistence-unavailable", error=type(exc).__name__, pending=str(pending_path)
        )
        raise

    _write_artifact(
        artifact_path,
        artifact_items,
        started_at,
        feed_health=_collection_metadata.get("feedHealth", []),
    )

    result = {
        "state": "completed",
        "feeds": feed_count,
        "successfulFeeds": success_count,
        "items": len(items),
        "artifactItems": len(artifact_items),
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
    lock_path = settings.data_dir / "artifacts" / "radar" / "refresh.lock"
    lock_fd: int | None = None
    try:
        if settings.radar_refresh_startup_delay:
            await asyncio.sleep(settings.radar_refresh_startup_delay)
        lock_fd = _acquire_refresh_lock(lock_path, settings.radar_refresh_timeout)
        if lock_fd is None:
            _set_status("throttled", reason="another-process-refresh")
            return
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
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            with suppress(FileNotFoundError):
                lock_path.unlink()


def _acquire_refresh_lock(path: Path, stale_after_seconds: float) -> int | None:
    """Acquire a cross-process lock, recovering locks left by a crashed worker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode("ascii"))
            return fd
        except FileExistsError:
            try:
                age_seconds = datetime.now().timestamp() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if attempt == 0 and age_seconds > stale_after_seconds:
                with suppress(FileNotFoundError):
                    path.unlink()
                continue
            return None
    return None


def _collect_latest_news(settings: Settings) -> tuple[list[dict[str, Any]], int, int]:
    _collection_metadata.clear()
    feeds = parse_feeds_file(settings.radar_feeds_file)
    if not feeds:
        raise RuntimeError(f"No Radar feeds configured in {settings.radar_feeds_file}")

    started = perf_counter()
    fetcher = Fetcher(
        timeout=min(settings.http_timeout, 30),
        max_workers=settings.radar_fetch_workers,
        cache_max_age_hours=settings.radar_refresh_min_interval_minutes / 60,
    )
    results = fetcher.fetch_feeds(feeds, use_cache=True)
    _collection_metadata["feedHealth"] = [
        {
            "sourceId": result.source_id,
            "product": result.product,
            "channel": result.channel,
            "url": result.url,
            "status": result.status_code,
            "cached": result.is_cached,
            "ok": bool(result.status_code and result.status_code < 400),
            "error": result.error_message,
        }
        for result in results
    ]
    _collection_metadata["fetchDurationMs"] = round((perf_counter() - started) * 1000)
    success_count = sum(1 for result in results if result.status_code and result.status_code < 400)
    if success_count == 0:
        raise RuntimeError("All configured Radar feeds failed")
    extracted = []
    extractor = Extractor()
    for result, health in zip(results, _collection_metadata["feedHealth"], strict=True):
        entries = [item for item in extractor.extract(result) if item.confidence > 0]
        health["parsedItems"] = len(entries)
        health["parseOk"] = is_feed_content(result.content) if result.content_type == "rss" else bool(entries)
        health["ok"] = health["ok"] and health["parseOk"]
        extracted.extend(entries)
    success_count = sum(health["ok"] for health in _collection_metadata["feedHealth"])
    if not success_count:
        raise RuntimeError("No Radar feeds could be parsed")
    _collection_metadata["extractedItems"] = len(extracted)
    for item in extracted:
        item.feed_hash = hashlib.sha256(f"{item.title}\n{item.content}".encode()).hexdigest()
    normalizer = Normalizer()
    recent = _filter_recent_extracted_items(extracted, normalizer, settings.radar_days)
    _collection_metadata["recentItems"] = len(recent)
    for health in _collection_metadata["feedHealth"]:
        health["recentItems"] = sum(item.source_id == health["sourceId"] for item in recent)
    if settings.radar_fetch_full_articles and settings.radar_article_fetch_limit:
        preliminary = rank_items(
            normalizer.normalize(recent),
            days=settings.radar_days,
            max_items=settings.radar_max_items,
        )
        recent = _enrich_with_full_articles(
            recent,
            fetcher=Fetcher(
                timeout=min(settings.http_timeout, 30),
                max_workers=settings.radar_fetch_workers,
                cache_max_age_hours=24,
            ),
            limit=settings.radar_article_fetch_limit,
            previous_items=load_radar_artifact(settings).get("items") or [],
            preferred_urls={entry.item.url for entry in preliminary},
        )
    normalized = normalizer.normalize(recent)
    ranked = rank_items(normalized, days=settings.radar_days, max_items=settings.radar_max_items)
    items = deduplicate_radar_items([_ranked_item_to_data(item) for item in ranked])
    items = _enrich_ranked_items(items, ranked, settings)
    return items, len(feeds), success_count


def _enrich_with_full_articles(
    items: list[ExtractedItem],
    *,
    fetcher: Fetcher,
    limit: int,
    previous_items: list[dict[str, Any]] | None = None,
    preferred_urls: set[str] | None = None,
) -> list[ExtractedItem]:
    """Replace short feed snippets with cached full article text when available."""
    by_product: dict[str, deque[ExtractedItem]] = defaultdict(deque)
    for item in items:
        if preferred_urls is not None and item.url not in preferred_urls:
            continue
        by_product[item.product.casefold()].append(item)
    selected: list[ExtractedItem] = []
    while len(selected) < limit and any(by_product.values()):
        for queue in by_product.values():
            if queue:
                selected.append(queue.popleft())
                if len(selected) == limit:
                    break
    targets = [
        FetchTarget(
            url=item.url,
            product=item.product,
            channel=item.channel,
            source_id=item.source_id,
            authority=item.authority,
        )
        for item in selected
        if item.url.startswith(("http://", "https://"))
    ]
    results = fetcher.fetch_targets_concurrent(targets, use_cache=True)
    result_by_url = {result.url: result for result in results}
    extractor = Extractor()
    enriched_count = 0
    for item in selected:
        result = result_by_url.get(item.url)
        if result is None or result.content_type == "error" or not result.content:
            continue
        candidates = extractor.extract_html_items(result)
        article = next((candidate for candidate in candidates if candidate.confidence > 0), None)
        if article is None:
            continue
        # Known release/news layouts were scoped to the real article by Extractor.
        # A cleaner body can legitimately be shorter than the feed HTML.
        scoped_body = "github.com/" in item.url and "/releases/tag/" in item.url
        scoped_body = scoped_body or "postgresql.org/about/news/" in item.url
        if len(article.content) <= len(item.content) and not scoped_body:
            continue
        item.content = article.content
        if item.channel == "release":
            # Some release pages append older changelogs. Do not attribute them
            # to the current title version (e.g. RocksDB's zero-copy API break).
            headings = list(re.finditer(r"\b\d+\.\d+\.\d+\s*\(\d{4}-\d{2}-\d{2}\)", item.content))
            if len(headings) > 1:
                item.content = item.content[: headings[1].start()].strip()
        item.html_content = article.html_content
        item.author = article.author or item.author
        item.confidence = max(item.confidence, article.confidence)
        item.tags = list(dict.fromkeys([*item.tags, *article.tags]))[:8]
        enriched_count += 1
    _collection_metadata["articleCandidates"] = len(targets)
    _collection_metadata["articlesEnriched"] = enriched_count
    return items


def _filter_recent_extracted_items(
    items: list[ExtractedItem],
    normalizer: Normalizer,
    max_days: int,
    max_undated_per_product: int = 3,
) -> list[ExtractedItem]:
    """Bound the expensive similarity pass to recent, relevant feed entries."""
    now = utc_now()
    cutoff = now - timedelta(days=max_days)
    filtered: list[ExtractedItem] = []
    undated_counts: dict[str, int] = {}

    for item in items:
        published_at = normalizer.parse_date(item.published_at)
        if published_at is not None:
            if cutoff <= published_at <= now + timedelta(hours=24):
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
    snippets = getattr(item, "snippets", [])
    tags = getattr(item, "tags", [])
    summary = _extractive_summary(item.content, snippets, title=item.title)
    if not item.content.strip() and item.content_type == "release":
        summary = "该发布条目未提供可提取的变更说明，请查阅原始发布页。"
    versions = extract_versions(item.title, "") if item.content_type == "release" else []
    components = [tag for tag in tags if tag in COMPONENT_KEYWORDS]
    content_hash = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
    source_text = " ".join(item.content.split())
    evidence_snippets = [text for text in snippets if text in source_text]
    if not evidence_snippets and source_text:
        evidence_snippets = [source_text[:240]]
    return {
        "id": radar_item_id(item.url),
        "url": item.url,
        "site": domain_from_url(item.url),
        "title": item.title,
        "originalTitle": item.title,
        "publishedDate": item.published_at[:10] if item.published_at else None,
        "product": item.product,
        "channel": getattr(item, "channel", "web"),
        "sourceId": getattr(item, "source_id", ""),
        "authority": getattr(item, "authority", "community"),
        "author": getattr(item, "author", None),
        "contentType": item.content_type,
        "summary": summary,
        "tags": tags,
        "version": versions[0] if versions else None,
        "components": components,
        "evidence": [{"text": snippet, "url": item.url} for snippet in evidence_snippets],
        "confidence": getattr(item, "confidence", 0.5),
        "score": getattr(ranked_item, "score", 0),
        "rank": getattr(ranked_item, "rank", None),
        "rankReasons": getattr(ranked_item, "reasons", []),
        "contentHash": content_hash,
        "feedHash": getattr(item, "feed_hash", ""),
        "analysisProvider": "extractive",
        "sources": item.sources,
        "fetchedAt": utc_now(),
        "rawContent": item.content,
        "syncBatch": date.today(),
    }


def _extractive_summary(content: str, snippets: list[str], *, title: str = "", max_length: int = 500) -> str:
    text = " ".join(content.split())
    if not text:
        return "暂无摘要，已保留原始链接以便后续阅读。"
    if title:
        title_index = text.casefold().find(title.casefold())
        if 0 <= title_index < 1000:
            text = text[title_index + len(title) :].lstrip(" :-–—") or text

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+|\s*\n+\s*", text)
        if len(sentence.strip()) >= 40
    ]
    candidates = [*sentences[:3], *snippets]
    selected: list[str] = []
    for candidate in candidates:
        normalized = " ".join(candidate.split())
        if not normalized:
            continue
        if any(
            normalized.casefold() in value.casefold() or value.casefold() in normalized.casefold()
            for value in selected
        ):
            continue
        selected.append(normalized)
        if len(" ".join(selected)) >= max_length:
            break

    summary = " ".join(selected) or text
    if len(summary) <= max_length:
        return summary
    clipped = summary[: max_length + 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped}…"


def _enrich_ranked_items(
    items: list[dict[str, Any]], ranked: list[Any], settings: Settings
) -> list[dict[str, Any]]:
    """Cache only successful, matching analyses; bound attempts and concurrent calls."""
    cached_items = load_radar_artifact(settings).get("items", [])
    pending_path = radar_artifact_path(settings).with_name("pending.json")
    with suppress(OSError, ValueError, AttributeError):
        cached_items = [*cached_items, *json.loads(pending_path.read_text(encoding="utf-8")).get("items", [])]
    previous_by_url = {canonicalize_radar_url(item["url"]): item for item in cached_items if item.get("url")}
    ranked_by_url = {canonicalize_radar_url(entry.item.url): entry for entry in ranked}
    model = settings.db_radar_model or settings.llm_model
    available = bool(settings.db_radar_api_key or settings.llm_api_key)
    budget = settings.radar_top_k if settings.radar_llm_enrichment_enabled and available else 0
    pending = []
    reused = 0
    insufficient = 0
    for item in items:
        key = canonicalize_radar_url(item["url"])
        previous = previous_by_url.get(key)
        if previous and (
            previous.get("contentHash") == item.get("contentHash")
            and previous.get("originalTitle") == item.get("originalTitle")
            and previous.get("analysisProvider") == "llm"
            and previous.get("analysisModel") == model
            and previous.get("promptVersion") == PROMPT_VERSION
        ):
            for field in (
                "title",
                "summary",
                "tags",
                "contentType",
                "evidence",
                "analysisProvider",
                "analysisModel",
                "promptVersion",
            ):
                item[field] = previous[field]
            reused += 1
            continue
        if len(item.get("rawContent", "")) < 80:
            insufficient += 1
            continue
        if len(pending) < budget and key in ranked_by_url:
            normalized = ranked_by_url[key].item
            extracted = ExtractedItem(
                url=normalized.url,
                product=normalized.product,
                title=normalized.title,
                content=normalized.content,
                html_content="",
                published_at=normalized.published_at,
                author=normalized.author,
                content_type=normalized.content_type,
                confidence=normalized.confidence,
                tags=normalized.tags,
            )
            pending.append((item, extracted))

    def analyze(entry):
        item, extracted = entry
        try:
            result = analyze_with_llm(extracted, IngestionRequest(url=extracted.url), settings=settings)
        except Exception as exc:
            logger.warning("Radar analysis failed: %s", type(exc).__name__)
            return False
        if result.get("analysis_provider") != "llm":
            return False
        item.update(
            title=result["title"],
            summary=result["summary"],
            contentType=result["content_type"],
            evidence=result["evidence"],
            analysisProvider="llm",
            analysisModel=model,
            promptVersion=PROMPT_VERSION,
        )
        item["tags"] = list(dict.fromkeys([*result["tags"], *item["tags"]]))[:8]
        if item["contentType"] != "release":
            item["version"] = None
        return True

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=min(4, max(1, settings.llm_max_concurrency))) as pool:
        outcomes = list(pool.map(analyze, pending))
    _collection_metadata.update(
        llmAttempts=len(pending),
        llmSucceeded=sum(outcomes),
        llmFailed=len(pending) - sum(outcomes),
        llmReused=reused,
        insufficientSourceItems=insufficient,
        analysisDurationMs=round((perf_counter() - started) * 1000),
    )
    return items


def _merge_incremental_items(
    current: list[dict[str, Any]], previous: list[dict[str, Any]], *, max_days: int
) -> list[dict[str, Any]]:
    """Keep recent prior items when individual sources are temporarily unavailable."""
    cutoff = (utc_now() - timedelta(days=max_days)).date()

    def still_relevant(item: dict[str, Any]) -> bool:
        value = item.get("publishedDate") or item.get("published_date")
        if not value:
            return True
        try:
            return date.fromisoformat(str(value)[:10]) >= cutoff
        except ValueError:
            return False

    current_urls = {canonicalize_radar_url(item["url"]) for item in current}
    merged = [
        *current,
        *(
            item
            for item in previous
            if still_relevant(item) and canonicalize_radar_url(item["url"]) not in current_urls
        ),
    ]
    merged.sort(
        key=lambda item: (
            float(item.get("score") or 0),
            str(item.get("publishedDate") or ""),
        ),
        reverse=True,
    )
    return merged


def _write_artifact(
    path: Path,
    items: list[dict[str, Any]],
    generated_at: datetime,
    *,
    feed_health: list[dict[str, Any]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "radar-startup-refresh",
        "generatedAt": generated_at.isoformat(),
        "latestSyncBatch": generated_at.date().isoformat(),
        "totalItems": len(items),
        "metrics": {
            **{key: value for key, value in _collection_metadata.items() if key != "feedHealth"},
            "fetchDurationMs": _collection_metadata.get("fetchDurationMs"),
            "articleCandidates": _collection_metadata.get("articleCandidates", 0),
            "articlesEnriched": _collection_metadata.get("articlesEnriched", 0),
            "successfulFeeds": sum(1 for feed in (feed_health or []) if feed.get("ok")),
            "failedFeeds": sum(1 for feed in (feed_health or []) if not feed.get("ok")),
        },
        "feedHealth": feed_health or [],
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
