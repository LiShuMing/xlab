from __future__ import annotations

from typing import Any

from tech_radar.collectors.opencli import create_opencli_collector
from tech_radar.llm import create_openai_enricher
from tech_radar.processors import QualityFilter, KeywordScorer, RuleTopicEnricher
from tech_radar.publishers.markdown import (
    create_jsonl_publisher,
    create_markdown_publisher,
)
from tech_radar.registry import PluginRegistry


def create_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register_collector("opencli", create_opencli_collector)
    registry.register_processor("quality-filter", _create_quality_filter)
    registry.register_processor("keyword-score", _create_keyword_scorer)
    registry.register_processor("topic-rule", lambda _options: RuleTopicEnricher())
    registry.register_processor("openai-enrich", create_openai_enricher)
    registry.register_publisher("markdown", create_markdown_publisher)
    registry.register_publisher("jsonl", create_jsonl_publisher)
    registry.load_entry_points()
    return registry


def _create_keyword_scorer(options: dict[str, Any]) -> KeywordScorer:
    raw_keywords = options.get("keywords", [])
    if not isinstance(raw_keywords, list) or not all(
        isinstance(keyword, str) for keyword in raw_keywords
    ):
        raise ValueError("processing.keywords must be a string array")
    return KeywordScorer(
        raw_keywords,
        keyword_weight=float(options.get("keyword_weight", 10.0)),
        priority_weight=float(options.get("priority_weight", 2.0)),
        author_weights={
            str(author): float(weight)
            for author, weight in dict(options.get("author_weights", {})).items()
        },
    )


def _create_quality_filter(options: dict[str, Any]) -> QualityFilter:
    quality = options.get("quality", {})
    if not isinstance(quality, dict):
        raise ValueError("processing.quality must be a table")
    negative_keywords = quality.get("negative_keywords", [])
    if not isinstance(negative_keywords, list) or not all(
        isinstance(keyword, str) for keyword in negative_keywords
    ):
        raise ValueError("processing.quality.negative_keywords must be strings")
    hard_negative_keywords = quality.get("hard_negative_keywords", [])
    if not isinstance(hard_negative_keywords, list) or not all(
        isinstance(keyword, str) for keyword in hard_negative_keywords
    ):
        raise ValueError(
            "processing.quality.hard_negative_keywords must be strings"
        )
    personal_relevance_keywords = quality.get(
        "personal_relevance_keywords", []
    )
    if not isinstance(personal_relevance_keywords, list) or not all(
        isinstance(keyword, str) for keyword in personal_relevance_keywords
    ):
        raise ValueError(
            "processing.quality.personal_relevance_keywords must be strings"
        )
    required_keywords = quality.get("required_keywords", [])
    if not isinstance(required_keywords, list) or not all(
        isinstance(keyword, str) for keyword in required_keywords
    ):
        raise ValueError("processing.quality.required_keywords must be strings")
    return QualityFilter(
        minimum_length=int(quality.get("minimum_length", 24)),
        negative_keywords=negative_keywords,
        hard_negative_keywords=hard_negative_keywords,
        personal_relevance_keywords=personal_relevance_keywords,
        required_keywords=required_keywords,
        protect_priority=int(quality.get("protect_priority", 100)),
    )
