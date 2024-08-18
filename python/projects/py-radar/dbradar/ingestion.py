"""Single-link ingestion pipeline for DB Radar admin submissions."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import socket
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from dateutil import parser as date_parser

from dbradar.config import get_config
from dbradar.extractor import ExtractedItem, Extractor
from dbradar.fetcher import Fetcher
from dbradar.job_store import IngestionJobStore
from dbradar.storage import DuckDBStore, StorageItem

logger = logging.getLogger(__name__)


CONTENT_TYPES = {"release", "benchmark", "blog", "news", "tutorial", "paper", "engine", "other"}


@dataclass
class IngestionRequest:
    url: str
    product: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    note: str = ""


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


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date_parser.parse(value).date()
    except (ValueError, TypeError, OverflowError):
        return None


def item_id_from_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def extract_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def select_best_item(items: List[ExtractedItem], target_url: str) -> ExtractedItem:
    if not items:
        raise ValueError("未能从链接中抽取内容")

    exact = [item for item in items if item.url == target_url]
    candidates = exact or items
    return sorted(candidates, key=lambda item: item.confidence, reverse=True)[0]


def analyze_with_llm(extracted: ExtractedItem, request: IngestionRequest) -> Dict[str, Any]:
    config = get_config()
    if not config.api_key or not config.base_url:
        analysis = fallback_analysis(extracted, request)
        analysis["analysis_provider"] = "fallback"
        return analysis

    prompt = f"""你是一位数据库领域研究编辑。请分析下面的文章，并只输出 JSON。

输出字段:
- title: 中文或原文标题，保留技术名词
- summary: 必须使用中文，150-280 字，说明核心内容、技术点和为什么值得读
- product: 文章涉及的产品、项目或来源
- content_type: release, benchmark, blog, news, tutorial, paper, engine, other 之一
- tags: 3-6 个简短标签

要求:
- 只输出 JSON，不要 Markdown，不要解释
- summary 必须是中文自然语言
- tags 使用中文或常见英文技术词均可

用户补充:
product: {request.product or ""}
source: {request.source or ""}
tags: {", ".join(request.tags)}
note: {request.note or ""}

文章:
URL: {extracted.url}
标题: {extracted.title}
来源: {extracted.product}
类型: {extracted.content_type}
正文:
{extracted.content[:6000]}
"""

    try:
        logger.info("Analyzing link with LLM model=%s base_url=%s", config.model, config.base_url)
        with httpx.Client(timeout=config.timeout) as client:
            response = client.post(
                f"{config.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key}",
                },
                json={
                    "model": config.model,
                    "max_tokens": 900,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            analysis = normalize_analysis(parse_json_object(content), extracted, request)
            analysis["analysis_provider"] = "llm"
            return analysis
    except Exception as exc:
        logger.exception("LLM analysis failed")
        raise RuntimeError(f"LLM analysis failed: {exc}") from exc


def parse_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def normalize_analysis(data: Dict[str, Any], extracted: ExtractedItem, request: IngestionRequest) -> Dict[str, Any]:
    tags = data.get("tags") or request.tags or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    content_type = data.get("content_type") or extracted.content_type or "blog"
    if content_type not in CONTENT_TYPES:
        content_type = "other"

    return {
        "title": data.get("title") or extracted.title,
        "summary": data.get("summary") or fallback_summary(extracted.content),
        "product": data.get("product") or request.product or extracted.product or extract_domain(extracted.url),
        "content_type": content_type,
        "tags": tags[:6],
    }


def fallback_analysis(extracted: ExtractedItem, request: IngestionRequest) -> Dict[str, Any]:
    return {
        "title": extracted.title,
        "summary": fallback_summary(extracted.content),
        "product": request.product or extracted.product or extract_domain(extracted.url),
        "content_type": extracted.content_type if extracted.content_type in CONTENT_TYPES else "blog",
        "tags": request.tags[:6],
    }


def fallback_summary(content: str) -> str:
    text = " ".join(content.split())
    if not text:
        return "暂无摘要，已保存原始链接以便后续阅读。"
    return text[:280] + ("..." if len(text) > 280 else "")


def ingest_link(job_id: str, request: IngestionRequest, data_dir, submitted_by: str = "admin") -> Dict[str, Any]:
    job_store = IngestionJobStore(data_dir=data_dir)
    store = DuckDBStore(data_dir=data_dir, db_name="items.duckdb")
    try:
        url = validate_public_url(request.url)
        if store.exists(url):
            item = store.get_by_id(item_id_from_url(url))
            job_store.update_job(job_id, "duplicate", item_id=item.id if item else None)
            return {"status": "duplicate", "item": item.to_dict() if item else None}

        job_store.update_job(job_id, "fetching")
        fetcher = Fetcher(timeout=30)
        with httpx.Client(timeout=30) as client:
            result = fetcher._fetch_single(client, url, request.product or request.source or extract_domain(url))
        if result.content_type == "error":
            raise ValueError(result.error_message or "抓取失败")

        job_store.update_job(job_id, "extracting")
        extracted = select_best_item(Extractor().extract(result), url)

        job_store.update_job(job_id, "analyzing")
        analysis = analyze_with_llm(extracted, request)

        job_store.update_job(job_id, "saving", metadata={"analysis": analysis})
        item = StorageItem(
            id=item_id_from_url(url),
            url=url,
            title=analysis["title"],
            original_title=extracted.title,
            published_date=parse_date(extracted.published_at) or date.today(),
            product=analysis["product"],
            content_type=analysis["content_type"],
            summary=analysis["summary"],
            tags=analysis["tags"],
            sources=[],
            raw_content=extracted.content,
            sync_batch=date.today(),
        )
        store.insert([item])
        job_store.update_job(job_id, "completed", item_id=item.id)
        return {"status": "completed", "item": item.to_dict()}
    except Exception as exc:
        logger.exception("Failed to ingest %s", request.url)
        job_store.update_job(job_id, "failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        store.close()
        job_store.close()
