"""Version history tool - tracks changelogs, deprecations, and pricing changes."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from ..types import ResearchOptions, ToolResult, VersionHistory
from ..web_search import WebSearchClient, create_web_search_client

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Prompt for extracting version history
HISTORY_PROMPT = """\
You are an AI product analyst. Extract version history information for {product} from the following search results.

Focus on:
1. Recent versions/releases (last 12 months)
2. Deprecated features
3. Pricing changes
4. Breaking changes

Search Results:
{search_results}

Return a JSON object with:
- versions: array of {version: string, date: string, highlights: array of strings}
- deprecations: array of deprecated feature descriptions
- pricing_changes: array of {date: string, change: string, old_price: string, new_price: string}

Return ONLY the JSON object.
"""


class HistoryTool:
    """Tool for tracking version history and changelogs."""

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
        options: ResearchOptions | None = None,
    ) -> ToolResult:
        """Track version history for an LLM API product.

        Args:
            product_name: The product to track history for.
            options: Research options.

        Returns:
            ToolResult with VersionHistory data.
        """
        try:
            log.info("history_tracking_started", product=product_name)

            # Search for changelog and release notes
            sources = []
            queries = [
                f"{product_name} changelog release notes 2024 2025",
                f"{product_name} pricing changes history",
                f"{product_name} deprecated features announcements",
            ]

            all_results = []
            for query in queries:
                results = await self.web_search.search(query, max_results=3)
                all_results.extend(results)
                sources.extend(r.url for r in results if r.url)

            # Deduplicate sources
            sources = list(set(sources))

            if not all_results:
                log.info("no_history_found", product=product_name)
                return ToolResult.ok(
                    data=VersionHistory.empty(product_name),
                    sources=[],
                )

            # Extract history using LLM
            history = await self._extract_history(product_name, all_results)

            return ToolResult.ok(data=history, sources=sources)

        except Exception as exc:
            log.error("history_tracking_failed", error=str(exc))
            return ToolResult.fail(str(exc))

    async def _extract_history(
        self,
        product_name: str,
        search_results: list,
    ) -> VersionHistory:
        """Extract version history using LLM."""
        try:
            # Format search results
            results_text = "\n\n".join(
                f"Source: {r.url}\nTitle: {r.title}\nContent: {r.snippet}"
                for r in search_results[:6]  # Limit to avoid token limits
            )

            message = await self.llm_client.messages.create(
                model=os.environ.get("LLM_MODEL", "qwen-max"),
                max_tokens=2048,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": HISTORY_PROMPT.format(
                            product=product_name,
                            search_results=results_text,
                        ),
                    }
                ],
            )

            content = self._extract_text(message)
            data = json.loads(content)

            return VersionHistory(
                product=product_name,
                versions=data.get("versions", []),
                deprecations=data.get("deprecations", []),
                pricing_changes=data.get("pricing_changes", []),
            )

        except Exception as exc:
            log.warning("history_extraction_failed", error=str(exc))
            return VersionHistory.empty(product_name)

    def _extract_text(self, message) -> str:
        """Extract text content from LLM response."""
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return str(message.content[0]) if message.content else ""