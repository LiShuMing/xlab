"""Shared lightweight content classification helpers."""

from __future__ import annotations

import re

RELEASE_KEYWORDS = (
    "release",
    "released",
    "announcing",
    "announcement",
    "version",
    "changelog",
    "what's new",
)
ENGINE_KEYWORDS = (
    "query",
    "execution",
    "optimizer",
    "scan",
    "join",
    "filter",
    "aggregate",
    "vectorized",
    "codegen",
    "mpp",
)
PERFORMANCE_KEYWORDS = (
    "performance",
    "benchmark",
    "speed",
    "optimize",
    "fast",
    "faster",
    "latency",
    "throughput",
)
RELEVANCE_KEYWORDS = (
    "database",
    "db",
    "olap",
    "query",
    "sql",
    "analytics",
    "storage",
    "index",
    "partition",
    "materialized",
    "view",
    "lakehouse",
    "warehouse",
    "data",
    "table",
    "column",
    "parquet",
    "duckdb",
    "clickhouse",
    "trino",
    "spark",
)
SNIPPET_KEYWORDS = (
    "performance",
    "query",
    "execute",
    "optimize",
    "update",
    "feature",
    "release",
    "new",
    "improve",
    "storage",
    "engine",
    "support",
    "introduce",
    "announce",
)
RELEASE_VERSION_RE = re.compile(r"v\d+\.")


def classify_content(title: str, content: str) -> str:
    """Classify technical content into the Radar content taxonomy."""
    text = f"{title} {content}".lower()
    if any(keyword in text for keyword in RELEASE_KEYWORDS) or RELEASE_VERSION_RE.search(text):
        return "release"
    if any(keyword in text for keyword in ENGINE_KEYWORDS):
        return "engine"
    if any(keyword in text for keyword in PERFORMANCE_KEYWORDS):
        return "performance"
    if "docs" in text or "documentation" in text:
        return "docs"
    if "blog" in text or "post" in text:
        return "blog"
    return "other"


def relevance_confidence(title: str, content: str, *, base: float = 0.3) -> float:
    """Estimate database/OLAP relevance using shared keyword heuristics."""
    text = f"{title} {content}".lower()
    score = base + sum(0.05 for keyword in RELEVANCE_KEYWORDS if keyword in text)
    if any(keyword in text for keyword in RELEASE_KEYWORDS):
        score += 0.2
    return min(score, 1.0)


def keyword_snippets(content: str, *, max_length: int = 200, limit: int = 3) -> list[str]:
    """Extract short sentences that contain shared technical keywords."""
    snippets: list[str] = []
    for sentence in re.split(r"[.!?\n]", content):
        sentence = sentence.strip()
        if 30 < len(sentence) < max_length and any(
            keyword in sentence.lower() for keyword in SNIPPET_KEYWORDS
        ):
            snippets.append(sentence)
    return snippets[:limit]
