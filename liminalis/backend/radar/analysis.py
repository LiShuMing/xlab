"""Radar content analysis helpers.

This module is storage-free by design. Fetching/extraction code can call it
from background workers, CLIs, or tests without pulling in a persistence layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend._shared.json_tools import load_json_object
from backend._shared.llm import ChatMessage, LLMRuntimeConfig, SyncLLMClient
from backend._shared.serializers import domain_from_url
from backend.radar.config import get_config
from backend.radar.extractor import ExtractedItem

logger = logging.getLogger(__name__)

CONTENT_TYPES = {"release", "benchmark", "blog", "news", "tutorial", "paper", "engine", "other"}


@dataclass
class IngestionRequest:
    url: str
    product: str = ""
    source: str = ""
    tags: list[str] = field(default_factory=list)
    note: str = ""


def analyze_with_llm(extracted: ExtractedItem, request: IngestionRequest) -> dict[str, Any]:
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
        client = SyncLLMClient(
            LLMRuntimeConfig(
                api_key=config.api_key,
                base_url=config.base_url or "https://api.openai.com/v1",
                model=config.model,
                timeout=config.timeout,
                max_tokens=900,
            )
        )
        try:
            content = client.complete(
                [ChatMessage(role="user", content=prompt)],
                max_tokens=900,
            ).text
        finally:
            client.close()
        analysis = normalize_analysis(load_json_object(content), extracted, request)
        analysis["analysis_provider"] = "llm"
        return analysis
    except Exception as exc:
        logger.exception("LLM analysis failed")
        raise RuntimeError(f"LLM analysis failed: {exc}") from exc


def normalize_analysis(
    data: dict[str, Any], extracted: ExtractedItem, request: IngestionRequest
) -> dict[str, Any]:
    tags = data.get("tags") or request.tags or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    content_type = data.get("content_type") or extracted.content_type or "blog"
    if content_type not in CONTENT_TYPES:
        content_type = "other"

    return {
        "title": data.get("title") or extracted.title,
        "summary": data.get("summary") or fallback_summary(extracted.content),
        "product": data.get("product")
        or request.product
        or extracted.product
        or domain_from_url(extracted.url),
        "content_type": content_type,
        "tags": tags[:6],
    }


def fallback_analysis(extracted: ExtractedItem, request: IngestionRequest) -> dict[str, Any]:
    return {
        "title": extracted.title,
        "summary": fallback_summary(extracted.content),
        "product": request.product or extracted.product or domain_from_url(extracted.url),
        "content_type": extracted.content_type if extracted.content_type in CONTENT_TYPES else "blog",
        "tags": request.tags[:6],
    }


def fallback_summary(content: str) -> str:
    text = " ".join(content.split())
    if not text:
        return "暂无摘要，已保存原始链接以便后续阅读。"
    return text[:280] + ("..." if len(text) > 280 else "")
