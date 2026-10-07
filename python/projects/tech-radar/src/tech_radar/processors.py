from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Any, Mapping

from tech_radar.domain import Signal


def _contains_keyword(text: str, keyword: str) -> bool:
    folded_keyword = keyword.casefold().strip()
    if not folded_keyword:
        return False
    if len(folded_keyword) <= 3:
        return bool(
            re.search(
                rf"(?<!\w){re.escape(folded_keyword)}(?!\w)",
                text,
            )
        )
    return folded_keyword in text


class KeywordScorer:
    """Deterministic baseline; an LLM processor can replace or follow it."""

    def __init__(
        self,
        keywords: Sequence[str],
        keyword_weight: float = 10.0,
        priority_weight: float = 2.0,
        author_weights: Mapping[str, float] | None = None,
    ) -> None:
        self.keywords = tuple(keyword.casefold() for keyword in keywords)
        self.keyword_weight = keyword_weight
        self.priority_weight = priority_weight
        self.author_weights = {
            author.lstrip("@").casefold(): float(weight)
            for author, weight in (author_weights or {}).items()
        }

    def process(self, signals: Sequence[Signal]) -> list[Signal]:
        ranked: list[Signal] = []
        for signal in signals:
            text = " ".join(
                (signal.title, signal.content, signal.author, *signal.tags)
            ).casefold()
            keyword_score = sum(
                self.keyword_weight for keyword in self.keywords if keyword in text
            )
            engagement = sum(
                max(float(value), 0.0) for value in signal.metrics.values()
            )
            priority_score = signal.priority * self.priority_weight
            author_score = self.author_weights.get(
                signal.author.lstrip("@").casefold(), 0.0
            )
            ranked.append(
                signal.with_score(
                    priority_score
                    + keyword_score
                    + author_score
                    + math.log1p(engagement)
                )
            )
        return sorted(ranked, key=lambda item: item.score, reverse=True)


class QualityFilter:
    def __init__(
        self,
        *,
        minimum_length: int = 24,
        negative_keywords: Sequence[str] = (),
        hard_negative_keywords: Sequence[str] = (),
        personal_relevance_keywords: Sequence[str] = (),
        required_keywords: Sequence[str] = (),
        protect_priority: int = 100,
    ) -> None:
        self.minimum_length = minimum_length
        self.negative_keywords = tuple(
            keyword.casefold() for keyword in negative_keywords
        )
        self.hard_negative_keywords = tuple(
            keyword.casefold() for keyword in hard_negative_keywords
        )
        self.personal_relevance_keywords = tuple(
            keyword.casefold() for keyword in personal_relevance_keywords
        )
        self.required_keywords = tuple(
            keyword.casefold() for keyword in required_keywords
        )
        self.protect_priority = protect_priority

    def process(self, signals: Sequence[Signal]) -> list[Signal]:
        accepted: list[Signal] = []
        seen_content: set[str] = set()
        for signal in signals:
            content_text = " ".join((signal.title, signal.content)).strip()
            filter_text = " ".join(
                (
                    content_text,
                    signal.author,
                    signal.url,
                    *signal.tags,
                )
            ).strip()
            folded_filter = filter_text.casefold()
            normalized_content = re.sub(
                r"\W+", " ", content_text.casefold()
            ).strip()
            normalized_filter = re.sub(
                r"\W+", " ", filter_text.casefold()
            ).strip()
            if not normalized_content:
                continue
            fingerprint = normalized_content[:500]
            if fingerprint in seen_content:
                continue
            if any(
                keyword in normalized_filter
                for keyword in self.hard_negative_keywords
            ):
                continue
            if self.required_keywords and not any(
                _contains_keyword(folded_filter, keyword)
                for keyword in self.required_keywords
            ):
                continue
            if (
                signal.priority >= self.protect_priority
                and self.personal_relevance_keywords
                and not any(
                    _contains_keyword(folded_filter, keyword)
                    for keyword in self.personal_relevance_keywords
                )
            ):
                continue
            if signal.priority < self.protect_priority:
                if len(normalized_content) < self.minimum_length:
                    continue
                if any(
                    keyword in normalized_filter
                    for keyword in self.negative_keywords
                ):
                    continue
            seen_content.add(fingerprint)
            accepted.append(signal)
        return accepted


class PassthroughProcessor:
    def process(self, signals: Sequence[Signal]) -> list[Signal]:
        return list(signals)


DEFAULT_TOPICS: tuple[dict[str, Any], ...] = (
    {
        "name": "数据库与查询引擎",
        "keywords": (
            "database", "olap", "sql", "query", "optimizer", "clickhouse",
            "starrocks", "duckdb", "datafusion", "postgres", "mysql",
        ),
        "why": "可能影响查询性能、执行引擎设计或数据库架构选型。",
        "angle": "从架构变化、性能收益、适用边界和同类实现对比四个角度展开。",
    },
    {
        "name": "存储与硬件",
        "keywords": (
            "storage", "ssd", "nvme", "io_uring", "filesystem", "cache",
            "memory", "simd", "cpu", "gpu", "hardware",
        ),
        "why": "可能改变系统的 I/O、缓存、内存或计算瓶颈。",
        "angle": "分析硬件特征如何传导到软件栈，并给出可复现的基准验证方案。",
    },
    {
        "name": "Rust 与 C++",
        "keywords": (
            "rust", "cargo", "c++", "cpp", "clang", "gcc", "llvm",
            "compiler", "borrow checker",
        ),
        "why": "可能影响系统软件的性能、安全性、工具链或工程实践。",
        "angle": "结合可编译示例讨论语言机制、运行时成本与生产环境迁移代价。",
    },
    {
        "name": "Linux 与系统工程",
        "keywords": (
            "linux", "kernel", "ebpf", "bpf", "systemd", "container",
            "kubernetes", "scheduler", "networking",
        ),
        "why": "可能影响基础设施的可靠性、可观测性或资源调度。",
        "angle": "从内核机制、用户态接口、运维影响和故障边界进行拆解。",
    },
    {
        "name": "开源项目与工程工具",
        "keywords": (
            "github", "open source", "release", "benchmark", "library",
            "framework", "tooling", "cli",
        ),
        "why": "可能形成新的工程能力、依赖选择或开源协作机会。",
        "angle": "先验证项目成熟度，再分析核心设计、替代方案和采用成本。",
    },
)


class RuleTopicEnricher:
    def __init__(self, topics: Sequence[dict[str, Any]] = DEFAULT_TOPICS) -> None:
        self.topics = tuple(topics)

    def process(self, signals: Sequence[Signal]) -> list[Signal]:
        enriched: list[Signal] = []
        for signal in signals:
            haystack = " ".join(
                (signal.title, signal.content, signal.author, *signal.tags)
            ).casefold()
            ranked_topics: list[tuple[int, dict[str, Any]]] = []
            for topic in self.topics:
                matches = sum(
                    1
                    for keyword in topic.get("keywords", ())
                    if str(keyword).casefold() in haystack
                )
                if matches:
                    ranked_topics.append((matches, topic))
            if ranked_topics:
                matches, selected = max(ranked_topics, key=lambda item: item[0])
                topic_name = str(selected["name"])
                why = str(selected["why"])
                angle = str(selected["angle"])
            else:
                matches = 0
                topic_name = "其他技术动态"
                why = "这是你主动选择的内容，值得结合原文判断其长期技术价值。"
                angle = "先补充项目背景、核心变化和可验证证据，再决定是否展开写作。"
            summary = " ".join((signal.content or signal.title).split())[:240]
            relevance = min(100, 35 + signal.priority // 2 + matches * 10)
            enriched_signal = signal.with_annotations(
                topic=topic_name,
                summary_zh=summary,
                why_it_matters=why,
                writing_angle=angle,
                relevance=relevance,
                enrichment="rule",
            )
            enriched.append(enriched_signal.with_score(signal.score + relevance / 10))
        return sorted(enriched, key=lambda item: item.score, reverse=True)
