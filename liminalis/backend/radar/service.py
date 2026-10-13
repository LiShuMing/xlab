"""Async SQLAlchemy radar operations — replaces sync psycopg and DuckDB paths."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import case, func, literal, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.jobs import TERMINAL_JOB_STATUSES, JobStatus
from backend._shared.schemas import page_response
from backend._shared.serializers import domain_from_url, isoformat, utc_now
from backend.radar.db_models import RadarIngestionJob, RadarItem
from backend.radar.identity import canonicalize_radar_url, radar_item_id


async def query_radar_items(
    session: AsyncSession,
    *,
    page: int,
    per_page: int,
    content_type: str,
    product: str,
    query: str,
) -> dict[str, Any]:
    stmt = select(RadarItem)
    count_stmt = select(func.count(RadarItem.id))

    if content_type not in {"", "all"}:
        stmt = stmt.where(RadarItem.content_type == content_type)
        count_stmt = count_stmt.where(RadarItem.content_type == content_type)
    if product not in {"", "all"}:
        stmt = stmt.where(RadarItem.product == product)
        count_stmt = count_stmt.where(RadarItem.product == product)
    if query:
        ts_query = func.plainto_tsquery("simple", query)
        searchable = (
            func.coalesce(RadarItem.title, "")
            + literal(" ")
            + func.coalesce(RadarItem.original_title, "")
            + literal(" ")
            + func.coalesce(RadarItem.product, "")
            + literal(" ")
            + func.coalesce(RadarItem.summary, "")
        )
        ts_vector = func.to_tsvector("simple", searchable)
        predicate = ts_vector.op("@@")(ts_query) | func.array_to_string(RadarItem.tags, " ").icontains(
            query, autoescape=True
        )
        # PostgreSQL's simple dictionary does not segment Chinese words.
        if re.search(r"[\u4e00-\u9fff]", query):
            predicate = predicate | searchable.icontains(query, autoescape=True)
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)

    total_items: int = (await session.execute(count_stmt)).scalar_one()
    if total_items == 0:
        return page_response(
            items=[],
            page=page,
            per_page=per_page,
            total_items=0,
            products=[],
            contentTypes=[],
            latestSyncBatch=None,
        )

    offset = (page - 1) * per_page
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    RadarItem.sync_batch.desc().nullslast(),
                    RadarItem.score.desc(),
                    RadarItem.published_date.desc().nullslast(),
                    RadarItem.fetched_at.desc(),
                )
                .limit(per_page)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    product_counts = (
        await session.execute(
            select(RadarItem.product, func.count(RadarItem.id).label("count"))
            .where(RadarItem.product != "")
            .group_by(RadarItem.product)
            .order_by(text("count DESC"), RadarItem.product.asc())
            .limit(24)
        )
    ).all()

    type_counts = (
        await session.execute(
            select(RadarItem.content_type, func.count(RadarItem.id).label("count"))
            .where(RadarItem.content_type != "")
            .group_by(RadarItem.content_type)
            .order_by(text("count DESC"), RadarItem.content_type.asc())
        )
    ).all()

    latest_row = (await session.execute(select(func.max(RadarItem.sync_batch)))).scalar_one()

    return page_response(
        items=[radar_item_to_dict(item) for item in rows],
        page=page,
        per_page=per_page,
        total_items=total_items,
        **{
            "products": [{"name": name, "count": cnt} for name, cnt in product_counts],
            "contentTypes": [{"name": name, "count": cnt} for name, cnt in type_counts],
            "latestSyncBatch": latest_row.isoformat() if latest_row else None,
        },
    )


async def upsert_radar_item(session: AsyncSession, item_data: dict[str, Any]) -> RadarItem:
    canonical_url = canonicalize_radar_url(item_data["url"])
    stable_id = radar_item_id(canonical_url)
    item = RadarItem(**_radar_item_values(item_data, canonical_url, stable_id))
    candidate_ids = [stable_id, item_data.get("id"), *(item_data.get("legacy_ids") or [])]
    existing = None
    for candidate_id in dict.fromkeys(value for value in candidate_ids if value):
        existing = await session.get(RadarItem, candidate_id)
        if existing is not None:
            break
    if existing is None:
        candidate_urls = [item_data["url"], *(item_data.get("legacy_urls") or [])]
        existing = await _get_radar_item_by_urls(session, candidate_urls)
    if existing:
        _merge_radar_model(existing, item, item_data)
        session.add(existing)
        return existing
    session.add(item)
    return item


def _radar_item_values(item_data: dict[str, Any], canonical_url: str, stable_id: str) -> dict[str, Any]:
    return {
        "id": stable_id,
        "url": canonical_url,
        "title": item_data.get("title") or "",
        "original_title": item_data.get("original_title")
        or item_data.get("originalTitle")
        or item_data.get("title")
        or "",
        "published_date": _parse_date(item_data.get("published_date") or item_data.get("publishedDate")),
        "product": item_data.get("product") or "",
        "channel": item_data.get("channel") or "web",
        "source_id": item_data.get("source_id") or item_data.get("sourceId") or "",
        "authority": item_data.get("authority") or "community",
        "author": item_data.get("author"),
        "content_type": item_data.get("content_type") or item_data.get("contentType") or "blog",
        "summary": item_data.get("summary") or "",
        "tags": item_data.get("tags") or [],
        "sources": item_data.get("sources") or [],
        "fetched_at": _parse_datetime(item_data.get("fetched_at") or item_data.get("fetchedAt")) or utc_now(),
        "raw_content": item_data.get("raw_content") or item_data.get("rawContent") or "",
        "sync_batch": _parse_date(item_data.get("sync_batch") or item_data.get("syncBatch")),
        "version": item_data.get("version"),
        "components": item_data.get("components") or [],
        "evidence": item_data.get("evidence") or [],
        "confidence": float(item_data.get("confidence") or 0),
        "score": float(item_data.get("score") or 0),
        "rank": item_data.get("rank"),
        "rank_reasons": item_data.get("rank_reasons") or item_data.get("rankReasons") or [],
        "content_hash": item_data.get("content_hash") or item_data.get("contentHash") or "",
        "analysis_provider": item_data.get("analysis_provider")
        or item_data.get("analysisProvider")
        or "extractive",
        "analysis_model": item_data.get("analysis_model") or item_data.get("analysisModel"),
        "prompt_version": item_data.get("prompt_version") or item_data.get("promptVersion"),
    }


def _merge_radar_model(existing: RadarItem, item: RadarItem, item_data: dict[str, Any]) -> None:
    existing.url = item.url
    for key in (
        "title",
        "original_title",
        "product",
        "channel",
        "source_id",
        "authority",
        "author",
    ):
        incoming = getattr(item, key)
        if incoming:
            setattr(existing, key, incoming)
    for key in ("summary", "raw_content"):
        incoming = getattr(item, key)
        if len(incoming) > len(getattr(existing, key)):
            setattr(existing, key, incoming)
    incoming_content_type = item_data.get("content_type") or item_data.get("contentType")
    if incoming_content_type:
        existing.content_type = incoming_content_type
    existing.tags = _merge_values(existing.tags, item.tags)
    existing.sources = _merge_values(existing.sources, item.sources)
    existing.components = _merge_values(existing.components, item.components)
    existing.rank_reasons = item.rank_reasons or existing.rank_reasons
    existing.evidence = item.evidence or existing.evidence
    for key in (
        "version",
        "content_hash",
        "analysis_provider",
        "analysis_model",
        "prompt_version",
        "rank",
    ):
        incoming = getattr(item, key)
        if incoming not in (None, ""):
            setattr(existing, key, incoming)
    existing.confidence = max(existing.confidence or 0, item.confidence or 0)
    existing.score = item.score or existing.score
    existing.published_date = item.published_date or existing.published_date
    existing.fetched_at = _latest_value(existing.fetched_at, _parse_datetime_value(item.fetched_at))
    existing.sync_batch = _latest_value(existing.sync_batch, item.sync_batch)


async def get_radar_item_by_url(session: AsyncSession, url: str) -> RadarItem | None:
    return await _get_radar_item_by_urls(session, [url])


async def _get_radar_item_by_urls(session: AsyncSession, urls: list[str]) -> RadarItem | None:
    candidates: set[str] = set()
    for url in urls:
        candidates.add(url.strip())
        candidates.add(canonicalize_radar_url(url))
    result = await session.execute(select(RadarItem).where(RadarItem.url.in_(candidates)).limit(1))
    return result.scalar_one_or_none()


async def upsert_radar_items_bulk(session: AsyncSession, items: list[dict[str, Any]]) -> int:
    if not items:
        return 0

    rows_by_url: dict[str, dict[str, Any]] = {}
    for item_data in items:
        canonical_url = canonicalize_radar_url(item_data["url"])
        rows_by_url[canonical_url] = _radar_item_values(
            item_data,
            canonical_url,
            radar_item_id(canonical_url),
        )

    insert_stmt = pg_insert(RadarItem).values(list(rows_by_url.values()))
    incoming = insert_stmt.excluded
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[RadarItem.url],
        set_={
            "title": case((incoming.title != "", incoming.title), else_=RadarItem.title),
            "original_title": case(
                (incoming.original_title != "", incoming.original_title),
                else_=RadarItem.original_title,
            ),
            "published_date": func.coalesce(incoming.published_date, RadarItem.published_date),
            "product": case((incoming.product != "", incoming.product), else_=RadarItem.product),
            "channel": incoming.channel,
            "source_id": case((incoming.source_id != "", incoming.source_id), else_=RadarItem.source_id),
            "authority": incoming.authority,
            "author": func.coalesce(incoming.author, RadarItem.author),
            "content_type": incoming.content_type,
            "summary": incoming.summary,
            "tags": case((func.cardinality(incoming.tags) > 0, incoming.tags), else_=RadarItem.tags),
            "sources": case(
                (func.cardinality(incoming.sources) > 0, incoming.sources), else_=RadarItem.sources
            ),
            "fetched_at": func.greatest(incoming.fetched_at, RadarItem.fetched_at),
            "raw_content": incoming.raw_content,
            "sync_batch": func.greatest(incoming.sync_batch, RadarItem.sync_batch),
            "version": incoming.version,
            "components": incoming.components,
            "evidence": incoming.evidence,
            "confidence": func.greatest(incoming.confidence, RadarItem.confidence),
            "score": incoming.score,
            "rank": incoming.rank,
            "rank_reasons": incoming.rank_reasons,
            "content_hash": incoming.content_hash,
            "analysis_provider": incoming.analysis_provider,
            "analysis_model": incoming.analysis_model,
            "prompt_version": incoming.prompt_version,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return len(rows_by_url)


async def create_ingestion_job(
    session: AsyncSession,
    *,
    job_id: str,
    url: str,
    submitted_by: str = "",
    metadata: dict[str, Any] | None = None,
) -> RadarIngestionJob:
    job = RadarIngestionJob(
        id=job_id,
        url=canonicalize_radar_url(url),
        status=JobStatus.QUEUED.value,
        submitted_by=submitted_by,
        submitted_at=func.now(),
        metadata_=metadata or {},
    )
    session.add(job)
    await session.flush()
    return job


async def update_ingestion_job(
    session: AsyncSession,
    job_id: str,
    *,
    status: str | None = None,
    error: str | None = None,
    item_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RadarIngestionJob | None:
    job = await session.get(RadarIngestionJob, job_id)
    if not job:
        return None
    if status is not None:
        job.status = status
    if error is not None:
        job.error = error
    if item_id is not None:
        job.item_id = item_id
    if metadata is not None:
        job.metadata_ = metadata
    if status == JobStatus.FETCHING.value and job.started_at is None:
        job.started_at = func.now()
    if status in {state.value for state in TERMINAL_JOB_STATUSES} and job.completed_at is None:
        job.completed_at = func.now()
    session.add(job)
    await session.flush()
    return job


async def get_ingestion_job(session: AsyncSession, job_id: str) -> RadarIngestionJob | None:
    return await session.get(RadarIngestionJob, job_id)


async def list_ingestion_jobs(session: AsyncSession, limit: int = 30) -> list[RadarIngestionJob]:
    result = await session.execute(
        select(RadarIngestionJob).order_by(RadarIngestionJob.submitted_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


def radar_item_to_dict(item: RadarItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "originalTitle": item.original_title or item.title,
        "url": item.url,
        "site": domain_from_url(item.url),
        "product": item.product,
        "channel": item.channel,
        "sourceId": item.source_id,
        "authority": item.authority,
        "author": item.author,
        "summary": item.summary,
        "tags": item.tags or [],
        "sources": item.sources or [],
        "publishedDate": isoformat(item.published_date),
        "contentType": item.content_type,
        "version": item.version,
        "components": item.components or [],
        "evidence": item.evidence or [],
        "confidence": item.confidence,
        "score": item.score,
        "rank": item.rank,
        "rankReasons": item.rank_reasons or [],
        "contentHash": item.content_hash,
        "analysisProvider": item.analysis_provider,
        "analysisModel": item.analysis_model,
        "promptVersion": item.prompt_version,
        "fetchedAt": isoformat(item.fetched_at),
        "syncBatch": isoformat(item.sync_batch),
    }


def _job_to_dict(job: RadarIngestionJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "url": job.url,
        "status": job.status,
        "error": job.error,
        "item_id": job.item_id,
        "submitted_by": job.submitted_by,
        "submitted_at": isoformat(job.submitted_at),
        "started_at": isoformat(job.started_at),
        "completed_at": isoformat(job.completed_at),
        "metadata": job.metadata_,
    }


def ingestion_job_to_dict(job: RadarIngestionJob) -> dict[str, Any]:
    """Serialize an ingestion job for CLI/API callers."""
    return _job_to_dict(job)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
        return parsed if parsed.year > 1900 else None
    if isinstance(value, datetime):
        parsed = value.date()
        return parsed if parsed.year > 1900 else None
    if isinstance(value, str) and value:
        parsed = date.fromisoformat(value[:10])
        return parsed if parsed.year > 1900 else None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _parse_datetime_value(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _merge_values(existing: list[str] | None, incoming: list[str] | None) -> list[str]:
    return list(dict.fromkeys([*(existing or []), *(incoming or [])]))


def _latest_value(existing: Any, incoming: Any) -> Any:
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    try:
        return max(existing, incoming)
    except TypeError:
        return incoming
