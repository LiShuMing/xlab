"""Async SQLAlchemy radar operations — replaces sync psycopg and DuckDB paths."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.jobs import TERMINAL_JOB_STATUSES, JobStatus
from backend._shared.schemas import page_response
from backend._shared.serializers import domain_from_url, isoformat
from backend.radar.db_models import RadarIngestionJob, RadarItem


async def query_radar_items(
    session: AsyncSession,
    *,
    page: int,
    per_page: int,
    content_type: str,
    product: str,
    query: str,
) -> dict[str, Any] | None:
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
        ts_vector = func.to_tsvector(
            "simple",
            func.concat(
                func.coalesce(RadarItem.title, ""),
                " ",
                func.coalesce(RadarItem.original_title, ""),
                " ",
                func.coalesce(RadarItem.product, ""),
                " ",
                func.coalesce(RadarItem.content_type, ""),
                " ",
                func.coalesce(RadarItem.summary, ""),
                " ",
                func.array_to_string(RadarItem.tags, " "),
            ),
        )
        stmt = stmt.where(ts_vector.op("@@")(ts_query))
        count_stmt = count_stmt.where(ts_vector.op("@@")(ts_query))

    total_items: int = (await session.execute(count_stmt)).scalar_one()
    if total_items == 0:
        return None

    offset = (page - 1) * per_page
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    RadarItem.sync_batch.desc().nullslast(),
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
    item = RadarItem(
        id=item_data["id"],
        url=item_data["url"],
        title=item_data.get("title") or "",
        original_title=item_data.get("original_title")
        or item_data.get("originalTitle")
        or item_data.get("title")
        or "",
        published_date=_parse_date(item_data.get("published_date") or item_data.get("publishedDate")),
        product=item_data.get("product") or "",
        content_type=item_data.get("content_type") or item_data.get("contentType") or "blog",
        summary=item_data.get("summary") or "",
        tags=item_data.get("tags") or [],
        sources=item_data.get("sources") or [],
        fetched_at=_parse_datetime(item_data.get("fetched_at") or item_data.get("fetchedAt")) or func.now(),
        raw_content=item_data.get("raw_content") or item_data.get("rawContent") or "",
        sync_batch=_parse_date(item_data.get("sync_batch") or item_data.get("syncBatch")),
    )
    existing = await session.get(RadarItem, item.id)
    if existing:
        for key in (
            "url",
            "title",
            "original_title",
            "published_date",
            "product",
            "content_type",
            "summary",
            "tags",
            "sources",
            "fetched_at",
            "raw_content",
            "sync_batch",
        ):
            setattr(existing, key, getattr(item, key))
        session.add(existing)
        return existing
    session.add(item)
    return item


async def get_radar_item_by_url(session: AsyncSession, url: str) -> RadarItem | None:
    result = await session.execute(select(RadarItem).where(RadarItem.url == url).limit(1))
    return result.scalar_one_or_none()


async def upsert_radar_items_bulk(session: AsyncSession, items: list[dict[str, Any]]) -> int:
    for item_data in items:
        await upsert_radar_item(session, item_data)
    await session.flush()
    return len(items)


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
        url=url,
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
        "summary": item.summary,
        "tags": item.tags or [],
        "sources": item.sources or [],
        "publishedDate": isoformat(item.published_date),
        "contentType": item.content_type,
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
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
