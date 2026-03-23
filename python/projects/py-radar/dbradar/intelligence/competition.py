"""Competitive analysis for generating insights about products."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional, Set

import httpx

from dbradar.config import get_config
from dbradar.intelligence.types import CompetitiveInsight, ToolResult

if TYPE_CHECKING:
    from dbradar.summarizer import SummaryResult


class CompetitionAnalyzer:
    """Analyze competitive landscape from product updates."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        config = get_config()
        self.api_key = api_key or config.api_key
        self.base_url = base_url or config.base_url
        self.model = model or config.model or "qwen3.5-plus"
        self.timeout = config.timeout
        self.client = httpx.Client(timeout=self.timeout)

    def analyze(
        self,
        current_summary: SummaryResult,
        products: Optional[Set[str]] = None,
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
        products: Set[str],
    ) -> List[CompetitiveInsight]:
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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "max_tokens": 3000,
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
            return []

        # Parse JSON from response
        json_text = raw_text
        if "```json" in raw_text:
            json_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            json_text = raw_text.split("```")[1].split("```")[0]
        else:
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1
            if start >= 0 and end > start:
                json_text = raw_text[start:end]

        parsed = json.loads(json_text.strip())

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
    products: Optional[Set[str]] = None,
) -> ToolResult:
    """Convenience function to analyze competition."""
    analyzer = CompetitionAnalyzer()
    try:
        return analyzer.analyze(current_summary, products=products)
    finally:
        analyzer.close()