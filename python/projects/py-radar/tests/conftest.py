"""Shared test fixtures for dbradar tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from dbradar.intelligence.types import (
    CompetitiveInsight,
    TrendResult,
)
from dbradar.summarizer import SummaryResult


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def sample_summary_result() -> SummaryResult:
    """Create a sample SummaryResult for testing."""
    return SummaryResult(
        executive_summary=[
            "Major database releases this week from Snowflake and Databricks",
            "New vector search capabilities announced by multiple vendors",
        ],
        top_updates=[
            {
                "product": "Snowflake",
                "title": "Snowflake Cortex Now Generally Available",
                "what_changed": [
                    "AI and ML capabilities now production-ready",
                    "New vector search features",
                ],
                "why_it_matters": [
                    "Enables enterprise AI workloads natively",
                    "Competes directly with Databricks AI offerings",
                ],
                "sources": ["https://snowflake.com/blog/cortex-ga"],
            },
            {
                "product": "Databricks",
                "title": "Databricks Unity Catalog Updates",
                "what_changed": [
                    "Enhanced governance features",
                    "New metastore capabilities",
                ],
                "why_it_matters": [
                    "Improved data governance for enterprises",
                    "Better integration with AI workloads",
                ],
                "sources": ["https://databricks.com/blog/unity-updates"],
            },
            {
                "product": "ClickHouse",
                "title": "ClickHouse 24.1 Released",
                "what_changed": [
                    "Performance improvements",
                    "New aggregation functions",
                ],
                "why_it_matters": [
                    "Faster analytics queries",
                    "More flexible data processing",
                ],
                "sources": ["https://clickhouse.com/blog/24-1"],
            },
        ],
        release_notes=[
            {
                "product": "Snowflake",
                "version": "7.40",
                "date": "2024-01-15",
                "highlights": ["Cortex GA", "Vector search"],
            },
        ],
        themes=[
            "AI/ML integration",
            "Vector databases",
            "Governance",
        ],
        action_items=[
            "Evaluate Snowflake Cortex for AI workloads",
            "Review Databricks Unity Catalog governance features",
        ],
        raw_response="{}",
    )


@pytest.fixture
def historical_summaries(temp_output_dir: Path) -> list[dict]:
    """Create historical summary files for trend analysis testing.

    Uses dates relative to today to ensure they're within the lookback window.
    """
    summaries = []

    # Create summaries for the past 7 days (relative to today)
    now = datetime.now(timezone.utc)

    for i in range(7):
        # Calculate date properly using timedelta
        from datetime import timedelta
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")

        summary_data = {
            "themes": [
                "Performance optimization",
                "Cloud analytics",
                "AI integration" if i < 3 else "Machine learning",
            ],
            "top_updates": [
                {"product": "Snowflake", "title": f"Update {i}"},
                {"product": "Databricks", "title": f"Update {i}"},
            ],
        }

        file_path = temp_output_dir / f"{date_str}.json"
        file_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
        summaries.append({"date": date_str, "data": summary_data})

    return summaries


@pytest.fixture
def mock_llm_response_trends() -> dict:
    """Mock LLM response for trend analysis."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "emerging_topics": ["Vector databases", "RAG architectures"],
                        "declining_topics": ["Traditional OLAP"],
                        "recurring_themes": ["AI/ML integration", "Cloud analytics"],
                        "trend_velocity": {"Vector databases": 0.8, "Traditional OLAP": 0.3},
                    })
                }
            }
        ]
    }


@pytest.fixture
def mock_llm_response_competition() -> dict:
    """Mock LLM response for competition analysis."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps([
                        {
                            "product": "Snowflake",
                            "recent_moves": ["Cortex GA announced", "Vector search released"],
                            "positioning_changes": ["Positioning as AI-native data platform"],
                            "competitive_threats": ["Databricks AI features"],
                            "opportunities": ["Enterprise AI governance gap"],
                        },
                        {
                            "product": "Databricks",
                            "recent_moves": ["Unity Catalog enhancements", "AI model updates"],
                            "positioning_changes": ["Expanding beyond Spark to full data platform"],
                            "competitive_threats": ["Snowflake's native AI capabilities"],
                            "opportunities": ["Multi-cloud governance"],
                        },
                    ])
                }
            }
        ]
    }


@pytest.fixture
def sample_trend_result() -> TrendResult:
    """Create a sample TrendResult for testing."""
    return TrendResult(
        emerging_topics=["Vector databases", "RAG architectures"],
        declining_topics=["Traditional OLAP"],
        recurring_themes=["AI/ML integration", "Cloud analytics"],
        trend_velocity={"Vector databases": 0.8, "Traditional OLAP": 0.3},
    )


@pytest.fixture
def sample_competitive_insights() -> list[CompetitiveInsight]:
    """Create sample CompetitiveInsight list for testing."""
    return [
        CompetitiveInsight(
            product="Snowflake",
            recent_moves=["Cortex GA announced", "Vector search released"],
            positioning_changes=["Positioning as AI-native data platform"],
            competitive_threats=["Databricks AI features"],
            opportunities=["Enterprise AI governance gap"],
        ),
        CompetitiveInsight(
            product="Databricks",
            recent_moves=["Unity Catalog enhancements"],
            positioning_changes=["Expanding beyond Spark"],
            competitive_threats=["Snowflake native AI"],
            opportunities=["Multi-cloud governance"],
        ),
    ]