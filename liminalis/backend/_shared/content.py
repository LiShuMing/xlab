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
VERSION_RE = re.compile(r"\b(?:v(?:ersion)?\s*)?(\d+\.\d+(?:\.\d+){0,2}(?:[-+][a-z0-9.-]+)?)\b", re.I)

COMPONENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "optimizer": ("optimizer", "query planning", "cost model", "cardinality"),
    "execution": ("execution engine", "vectorized", "codegen", "pipeline"),
    "storage": ("storage", "compaction", "segment", "sstable", "index"),
    "lakehouse": ("lakehouse", "iceberg", "parquet", "delta lake", "hudi"),
    "streaming": ("streaming", "cdc", "change data capture", "watermark"),
    "security": ("security", "cve-", "vulnerability", "authentication"),
    "observability": ("observability", "telemetry", "metrics", "tracing"),
}


def classify_content(title: str, content: str) -> str:
    """Classify technical content into the Radar content taxonomy."""
    text = f"{title} {content}".lower()
    if re.search(r"\b(release[ds]?|changelog|what.s new)\b", title, re.I):
        return "release"
    if "benchmark" in text or "tpc-" in text:
        return "benchmark"
    if "paper" in text or "proceedings" in text or "arxiv" in text:
        return "paper"
    if "tutorial" in text or "how to" in text or "guide" in text:
        return "tutorial"
    if any(keyword in text for keyword in ENGINE_KEYWORDS):
        return "engine"
    if any(keyword in text for keyword in PERFORMANCE_KEYWORDS):
        return "performance"
    if "docs" in text or "documentation" in text:
        return "docs"
    if "blog" in text or "post" in text:
        return "blog"
    return "other"


def extract_versions(title: str, content: str) -> list[str]:
    """Extract likely semantic product versions without treating dates as versions."""
    text = f"{title} {content[:1000]}"
    versions: list[str] = []
    for match in VERSION_RE.finditer(text):
        version = match.group(1)
        first = int(version.split(".", 1)[0])
        if 1900 <= first <= 2100:
            continue
        if version not in versions:
            versions.append(version)
    return versions[:3]


def extract_technical_tags(title: str, content: str, product: str = "") -> list[str]:
    """Build stable, deterministic tags used before optional LLM enrichment."""
    text = f"{title} {content}".lower()
    tags = [product] if product else []
    tags.extend(
        component
        for component, keywords in COMPONENT_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    )
    if any(keyword in text for keyword in PERFORMANCE_KEYWORDS):
        tags.append("performance")
    if any(keyword in text for keyword in RELEASE_KEYWORDS) or RELEASE_VERSION_RE.search(text):
        tags.append("release")
    return list(dict.fromkeys(tag for tag in tags if tag))[:8]


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
    for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", content):
        sentence = sentence.strip().rstrip(".!?。！？")
        if 30 < len(sentence) < max_length and any(
            keyword in sentence.lower() for keyword in SNIPPET_KEYWORDS
        ):
            snippets.append(sentence)
    return snippets[:limit]
