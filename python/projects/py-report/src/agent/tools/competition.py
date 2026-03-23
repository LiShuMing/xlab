"""Competitive comparison tool - generates side-by-side API comparisons."""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import structlog

from ..types import CompetitiveInsight, ResearchOptions, ToolResult
from ..web_search import WebSearchClient, create_web_search_client

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Default competitors for common LLM APIs
DEFAULT_COMPETITORS = {
    "openai": ["anthropic claude", "google gemini", "mistral"],
    "claude": ["openai gpt-4", "google gemini", "mistral"],
    "gpt-4": ["claude 3.5 sonnet", "gemini pro", "mistral large"],
    "gemini": ["gpt-4o", "claude 3.5 sonnet", "mistral"],
    "qwen": ["gpt-4o", "claude 3.5 sonnet", "gemini pro"],
}

# Comparison dimensions
COMPARISON_DIMENSIONS = [
    "context_window",
    "pricing_input",
    "pricing_output",
    "latency",
    "multimodal",
    "function_calling",
    "fine_tuning",
]

# Prompt for competitive comparison
COMPETITION_PROMPT = """\
You are an AI product analyst. Generate a competitive comparison for {product} vs its competitors.

Products to compare: {products}

For each dimension, provide:
1. The value/metric for each product
2. A brief analysis of who leads and why

Dimensions to compare:
- Context window (tokens)
- Input pricing (per 1M tokens)
- Output pricing (per 1M tokens)
- Latency (TTFT in ms)
- Multimodal capabilities (yes/no/partial)
- Function calling support (yes/no)
- Fine-tuning availability (yes/no)

Return a JSON array of objects with:
- dimension: the dimension name
- comparisons: object mapping product name to value
- analysis: 1-2 sentence insight

Return ONLY the JSON array.
"""


class CompetitionTool:
    """Tool for generating competitive comparisons."""

    def __init__(
        self,
        llm_client,  # AsyncAnthropic client
        web_search: WebSearchClient | None = None,
    ):
        self.llm_client = llm_client
        self.web_search = web_search or create_web_search_client()

    async def run(
        self,
        product_name: str,
        competitors: list[str] | None = None,
        options: ResearchOptions | None = None,
    ) -> ToolResult:
        """Generate competitive comparison insights.

        Args:
            product_name: The primary product to compare.
            competitors: List of competitor names. If None, uses defaults.
            options: Research options.

        Returns:
            ToolResult with list of CompetitiveInsight objects.
        """
        try:
            # Determine competitors
            if not competitors:
                competitors = self._get_default_competitors(product_name)

            if not competitors:
                log.info("no_competitors_found", product=product_name)
                return ToolResult.ok(data=[], sources=[])

            all_products = [product_name] + competitors
            log.info(
                "competition_analysis_started",
                products=all_products,
            )

            # Search for comparison data
            sources = await self._search_comparison_data(product_name, competitors)

            # Generate comparison using LLM
            insights = await self._generate_comparison(product_name, competitors)

            return ToolResult.ok(data=insights, sources=sources)

        except Exception as exc:
            log.error("competition_analysis_failed", error=str(exc))
            return ToolResult.fail(str(exc))

    def _get_default_competitors(self, product_name: str) -> list[str]:
        """Get default competitors based on product name."""
        product_lower = product_name.lower()
        for key, competitors in DEFAULT_COMPETITORS.items():
            if key in product_lower:
                return competitors
        return []

    async def _search_comparison_data(
        self,
        product_name: str,
        competitors: list[str],
    ) -> list[str]:
        """Search for comparison data and return source URLs."""
        sources = []
        queries = [
            f"{product_name} vs {' vs '.join(competitors)} comparison",
            f"{product_name} pricing benchmarks 2024",
        ]

        for query in queries:
            results = await self.web_search.search(query, max_results=3)
            sources.extend(r.url for r in results if r.url)

        return list(set(sources))

    async def _generate_comparison(
        self,
        product_name: str,
        competitors: list[str],
    ) -> list[CompetitiveInsight]:
        """Generate competitive insights using LLM."""
        all_products = [product_name] + competitors

        try:
            message = await self.llm_client.messages.create(
                model=os.environ.get("LLM_MODEL", "qwen-max"),
                max_tokens=2048,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": COMPETITION_PROMPT.format(
                            product=product_name,
                            products=", ".join(all_products),
                        ),
                    }
                ],
            )

            content = self._extract_text(message)
            insights_data = json.loads(content)

            return [
                CompetitiveInsight(
                    dimension=i.get("dimension", ""),
                    comparisons=i.get("comparisons", {}),
                    analysis=i.get("analysis", ""),
                )
                for i in insights_data
            ]

        except Exception as exc:
            log.warning("comparison_generation_failed", error=str(exc))
            return []

    def _extract_text(self, message) -> str:
        """Extract text content from LLM response."""
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return str(message.content[0]) if message.content else ""