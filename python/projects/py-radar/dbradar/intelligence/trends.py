"""Trend detection analyzer for identifying emerging and declining topics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import httpx

from dbradar.config import get_config
from dbradar.intelligence.types import ToolResult, TrendResult

if TYPE_CHECKING:
    from dbradar.ranker import RankedItem
    from dbradar.summarizer import SummaryResult


@dataclass
class HistoricalSummary:
    """A single historical summary from a previous run."""

    date: str
    themes: List[str]
    top_products: List[str]
    top_titles: List[str]


class TrendAnalyzer:
    """Analyze trends across historical summaries."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        config = get_config()
        self.output_dir = output_dir or config.output_dir
        self.api_key = api_key or config.api_key
        self.base_url = base_url or config.base_url
        self.model = model or config.model or "qwen3.5-plus"
        self.timeout = config.timeout
        self.client = httpx.Client(timeout=self.timeout)

    def get_historical_summaries(
        self, days: int = 14, min_summaries: int = 3
    ) -> List[HistoricalSummary]:
        """
        Load historical summaries from JSON files in output directory.

        Args:
            days: Number of days to look back.
            min_summaries: Minimum number of summaries needed for trend analysis.

        Returns:
            List of HistoricalSummary objects, sorted by date (oldest first).
        """
        summaries = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Find all JSON files that match date pattern
        for json_file in self.output_dir.glob("*.json"):
            if json_file.name == "fetched_items.json":
                continue

            try:
                # Parse date from filename (YYYY-MM-DD.json)
                file_date = json_file.stem
                dt = datetime.strptime(file_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                # Skip if outside the time window
                if dt < cutoff_date:
                    continue

                # Load the JSON
                data = json.loads(json_file.read_text(encoding="utf-8"))

                # Extract products from top_updates
                products = [u.get("product", "") for u in data.get("top_updates", [])]

                # Extract titles
                titles = [u.get("title", "") for u in data.get("top_updates", [])]

                summaries.append(
                    HistoricalSummary(
                        date=file_date,
                        themes=data.get("themes", []),
                        top_products=products,
                        top_titles=titles,
                    )
                )
            except (ValueError, json.JSONDecodeError, KeyError):
                continue

        # Sort by date (oldest first)
        summaries.sort(key=lambda s: s.date)

        # Only return if we have enough data
        if len(summaries) < min_summaries:
            return []

        return summaries

    def has_history(self, days: int = 7, min_summaries: int = 3) -> bool:
        """Check if there's enough historical data for trend analysis."""
        summaries = self.get_historical_summaries(days=days, min_summaries=min_summaries)
        return len(summaries) >= min_summaries

    def analyze(
        self,
        current_summary: SummaryResult,
        history_days: int = 14,
    ) -> ToolResult:
        """
        Analyze trends by comparing current summary with historical data.

        Args:
            current_summary: The current day's SummaryResult.
            history_days: Number of days of history to analyze.

        Returns:
            ToolResult containing TrendResult or error.
        """
        # Load historical summaries
        historical = self.get_historical_summaries(days=history_days)

        if not historical:
            return ToolResult.ok(TrendResult.empty())

        try:
            # Use LLM to analyze trends
            result = self._analyze_with_llm(current_summary, historical)
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(str(e))

    def _analyze_with_llm(
        self,
        current: SummaryResult,
        historical: List[HistoricalSummary],
    ) -> TrendResult:
        """Use LLM to identify trends."""

        # Build historical context
        historical_context = []
        for h in historical:
            historical_context.append(
                {
                    "date": h.date,
                    "themes": h.themes,
                    "top_products": h.top_products[:5],
                }
            )

        # Build current context
        current_context = {
            "themes": current.themes,
            "top_products": list(
                {u.get("product", "") for u in current.top_updates}
            ),
        }

        prompt = f"""You are a senior industry analyst specializing in database and OLAP technologies.

## Task
Analyze the following data to identify emerging and declining topics in the DB/OLAP industry.

## Historical Summaries (last {len(historical)} days)
{json.dumps(historical_context, indent=2, ensure_ascii=False)}

## Current Day Summary
{json.dumps(current_context, indent=2, ensure_ascii=False)}

## Analysis Instructions
1. **Emerging topics**: Topics that appear in current day but were rare or absent in historical data
2. **Declining topics**: Topics that were frequent in historical data but are absent or reduced in current day
3. **Recurring themes**: Topics that appear consistently across both historical and current data
4. **Trend velocity**: Rate of change for each emerging/declining topic (0.0 = stable, 1.0 = rapid change)

## Output Format
Return a JSON object with this structure (no markdown code blocks):
{{
    "emerging_topics": ["topic1", "topic2", "topic3"],
    "declining_topics": ["topic1", "topic2"],
    "recurring_themes": ["theme1", "theme2", "theme3"],
    "trend_velocity": {{"topic": 0.8}}
}}

Focus on meaningful trends, not trivial variations. Maximum 5 items per category."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Extract response text
        raw_text = ""
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                raw_text = choice["message"]["content"]

        if not raw_text:
            return TrendResult.empty()

        # Parse JSON from response
        json_text = raw_text
        if "```json" in raw_text:
            json_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            json_text = raw_text.split("```")[1].split("```")[0]
        else:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_text = raw_text[start:end]

        parsed = json.loads(json_text.strip())

        return TrendResult(
            emerging_topics=parsed.get("emerging_topics", [])[:5],
            declining_topics=parsed.get("declining_topics", [])[:5],
            recurring_themes=parsed.get("recurring_themes", [])[:5],
            trend_velocity=parsed.get("trend_velocity", {}),
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


def analyze_trends(
    current_summary: SummaryResult,
    history_days: int = 14,
) -> ToolResult:
    """Convenience function to analyze trends."""
    analyzer = TrendAnalyzer()
    try:
        return analyzer.analyze(current_summary, history_days=history_days)
    finally:
        analyzer.close()