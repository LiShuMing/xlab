"""Competitive analysis for generating insights about products."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend._shared.json_tools import load_json_array
from backend._shared.llm import ChatMessage, LLMRuntimeConfig, SyncLLMClient
from backend.radar.config import get_config
from backend.radar.intelligence.types import CompetitiveInsight, ToolResult

if TYPE_CHECKING:
    from backend.radar.summarizer import SummaryResult


class CompetitionAnalyzer:
    """Analyze competitive landscape from product updates."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        config = get_config()
        self.api_key = api_key or config.api_key
        self.base_url = base_url or config.base_url
        self.model = model or config.model or "qwen3.5-plus"
        self.timeout = config.timeout
        self.client = SyncLLMClient(
            LLMRuntimeConfig(
                api_key=self.api_key or "",
                base_url=self.base_url or "https://api.openai.com/v1",
                model=self.model,
                timeout=self.timeout,
                max_retries=2,
            )
        )

    def analyze(
        self,
        current_summary: SummaryResult,
        products: set[str] | None = None,
    ) -> ToolResult:
        """
        Generate competitive insights from product updates.

        Args:
            current_summary: The current day's SummaryResult.
            products: Set of products to analyze (extracted from top_updates if not provided).

        Returns:
            ToolResult containing list of CompetitiveInsight or error.
        """
        # Extract products from top_updates if not provided
        if products is None:
            products = {u.get("product", "") for u in current_summary.top_updates}

        # Remove empty products
        products = {p for p in products if p}

        # Need at least 2 products for meaningful competition analysis
        if len(products) < 2:
            return ToolResult.ok([])

        try:
            insights = self._analyze_with_llm(current_summary, products)
            return ToolResult.ok(insights)
        except Exception as e:
            return ToolResult.fail(str(e))

    def _analyze_with_llm(
        self,
        current: SummaryResult,
        products: set[str],
    ) -> list[CompetitiveInsight]:
        """Use LLM to generate competitive insights."""

        # Group updates by product
        updates_by_product: dict = {p: [] for p in products}
        for update in current.top_updates:
            product = update.get("product", "")
            if product in updates_by_product:
                updates_by_product[product].append(
                    {
                        "title": update.get("title", ""),
                        "what_changed": update.get("what_changed", []),
                    }
                )

        prompt = f"""You are a senior competitive intelligence analyst specializing in database and OLAP technologies.

## Task
Analyze the following product updates and generate competitive insights for each product.

## Products to Analyze
{json.dumps(list(products), indent=2)}

## Updates by Product
{json.dumps(updates_by_product, indent=2, ensure_ascii=False)}

## Analysis Instructions
For each product, provide:
1. **Recent moves**: Key announcements, releases, or changes (2-3 items)
2. **Positioning changes**: How their market position may have shifted (1-2 items)
3. **Competitive threats**: Areas where they are gaining ground on competitors (1-2 items)
4. **Opportunities**: Gaps or weaknesses that competitors could exploit (1-2 items)

## Output Format
Return a JSON array with this structure (no markdown code blocks):
[
  {{
    "product": "ProductName",
    "recent_moves": ["move1", "move2"],
    "positioning_changes": ["change1"],
    "competitive_threats": ["threat1"],
    "opportunities": ["opportunity1", "opportunity2"]
  }}
]

Only include products with meaningful updates. Maximum 5 products.
Be specific and factual — avoid speculation."""

        response = self.client.complete(
            [ChatMessage(role="user", content=prompt)],
            model=self.model,
            max_tokens=3000,
        )
        raw_text = response.text

        if not raw_text:
            return []

        parsed = load_json_array(raw_text)

        insights = []
        for item in parsed:
            insights.append(
                CompetitiveInsight(
                    product=item.get("product", ""),
                    recent_moves=item.get("recent_moves", []),
                    positioning_changes=item.get("positioning_changes", []),
                    competitive_threats=item.get("competitive_threats", []),
                    opportunities=item.get("opportunities", []),
                )
            )

        return insights

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


def analyze_competition(
    current_summary: SummaryResult,
    products: set[str] | None = None,
) -> ToolResult:
    """Convenience function to analyze competition."""
    analyzer = CompetitionAnalyzer()
    try:
        return analyzer.analyze(current_summary, products=products)
    finally:
        analyzer.close()
