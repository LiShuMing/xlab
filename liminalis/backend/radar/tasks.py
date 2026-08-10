"""arq background tasks for the radar domain.

M1-E replaces ThreadPoolExecutor-submitted sync functions with arq tasks
that write through async SQLAlchemy to PostgreSQL.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import socket
from datetime import date
from typing import Any
from urllib.parse import urlparse

from dateutil import parser as date_parser

from backend._shared.jobs import JobStatus
from backend._shared.serializers import domain_from_url, utc_now
from backend._shared.storage import business_uow
from backend.radar.analysis import IngestionRequest, analyze_with_llm
from backend.radar.extractor import ExtractedItem, Extractor
from backend.radar.fetcher import Fetcher
from backend.radar.service import (
    get_radar_item_by_url,
    radar_item_to_dict,
    update_ingestion_job,
    upsert_radar_item,
)

logger = logging.getLogger(__name__)

CONTENT_TYPES = {"release", "benchmark", "blog", "news", "tutorial", "paper", "engine", "other"}


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入有效的 http/https 链接")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("链接缺少 host")

    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("不允许抓取本机地址")

    try:
        addresses = socket.getaddrinfo(hostname, None)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("不允许抓取内网地址")
    except socket.gaierror as exc:
        raise ValueError("链接域名无法解析") from exc

    return url


async def ingest_link_task(
    ctx: dict[str, object],
    job_id: str,
    request_data: dict[str, Any],
    submitted_by: str = "admin",
) -> dict[str, Any]:
    """arq task — ingest a single URL and persist to PostgreSQL."""
    async with business_uow() as session:
        await _mark_status(session, job_id, JobStatus.FETCHING)

        url = validate_public_url(request_data["url"])
        product = request_data.get("product", "")
        source = request_data.get("source", "")
        tags = request_data.get("tags", [])[:6]
        note = request_data.get("note", "")

        # Duplicate check
        existing = await get_radar_item_by_url(session, url)
        if existing:
            await _mark_status(session, job_id, JobStatus.DUPLICATE, item_id=existing.id)
            return {"status": JobStatus.DUPLICATE.value, "item": radar_item_to_dict(existing)}

        # Blocking: fetch + extract + LLM analyze
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, _fetch_and_extract, url, product or source or domain_from_url(url)
            )
        except Exception:
            await _mark_status(session, job_id, JobStatus.FAILED, error="抓取失败")
            raise

        try:
            analysis = await loop.run_in_executor(None, _llm_analyze, result, product, source, tags, note)
        except Exception:
            await _mark_status(session, job_id, JobStatus.FAILED, error="AI 分析失败")
            raise

        # Save to PG
        item_id = _hash_url(url)
        item_data = {
            "id": item_id,
            "url": url,
            "title": analysis["title"],
            "original_title": result.get("title", ""),
            "published_date": _parse_date(result.get("published_at")),
            "product": analysis["product"],
            "content_type": analysis["content_type"],
            "summary": analysis["summary"],
            "tags": analysis["tags"],
            "sources": [],
            "fetched_at": utc_now(),
            "raw_content": result.get("content", ""),
            "sync_batch": date.today(),
        }
        await upsert_radar_item(session, item_data)
        await _mark_status(session, job_id, JobStatus.COMPLETED, item_id=item_id)

        return {"status": JobStatus.COMPLETED.value, "item": item_data}


async def _mark_status(
    session,
    job_id: str,
    status: JobStatus,
    *,
    error: str | None = None,
    item_id: str | None = None,
) -> None:
    await update_ingestion_job(session, job_id, status=status.value, error=error, item_id=item_id)
    await session.flush()


def _fetch_and_extract(url: str, product: str) -> dict[str, Any]:
    """Blocking: fetch URL and extract content."""
    fetcher = Fetcher(timeout=30)
    with fetcher._http_client() as client:
        result = fetcher._fetch_single(client, url, product)
    if result.content_type == "error":
        raise ValueError(result.error_message or "抓取失败")

    extractor = Extractor()
    extracted = _select_best_item(extractor.extract(result), url)
    return {
        "url": extracted.url or url,
        "title": extracted.title,
        "content": extracted.content,
        "published_at": extracted.published_at,
        "content_type": extracted.content_type,
        "product": extracted.product,
        "author": extracted.author,
        "confidence": extracted.confidence,
    }


def _llm_analyze(
    result: dict[str, Any],
    product: str,
    source: str,
    tags: list[str],
    note: str,
) -> dict[str, Any]:
    """Blocking: run LLM analysis on extracted content."""
    extracted = ExtractedItem(
        url=result.get("url", ""),
        product=result["product"],
        title=result["title"],
        content=result["content"],
        published_at=result["published_at"],
        content_type=result.get("content_type", "blog"),
        author=result.get("author", ""),
        confidence=result.get("confidence", 0.8),
    )
    request = IngestionRequest(
        url="",
        product=product,
        source=source,
        tags=tags,
        note=note,
    )
    return analyze_with_llm(extracted, request)


def _select_best_item(items: list[ExtractedItem], url: str) -> ExtractedItem:
    """Pick the highest-confidence item, or a fallback."""
    if not items:
        return ExtractedItem(
            url=url,
            product="",
            title="",
            content="",
            published_at="",
            content_type="blog",
            author="",
            confidence=0,
        )
    items.sort(key=lambda item: item.confidence, reverse=True)
    return items[0]


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date_parser.parse(value).date()
    except Exception:
        return None
