"""Technical documentation analyzer - extracts structured info from docs."""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import structlog

from ..types import ResearchOptions, TechnicalDocs, ToolResult
from ..web_search import WebSearchClient, create_web_search_client

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Prompt for extracting technical documentation info
DOCS_PROMPT = """\
You are an AI product analyst. Extract technical documentation information for {product} from the following search results.

Extract:
1. Model cards (model names, capabilities, limits)
2. API endpoints (list of endpoints)
3. SDK examples (language -> example code snippet)
4. Rate limits (requests per minute, tokens per minute)

Search Results:
{search_results}

Return a JSON object with:
- model_cards: array of {name: string, context_window: number, capabilities: array of strings}
- api_endpoints: array of endpoint paths (e.g., "/v1/chat/completions")
- sdk_examples: object mapping language name to a brief example
- rate_limits: object with rpm, tpm, other limits

Return ONLY the JSON object.
"""


class DocsAnalyzerTool:
    """Tool for analyzing technical documentation."""

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
        """Analyze technical documentation for an LLM API product.

        Args:
            product_name: The product to analyze docs for.
            options: Research options.

        Returns:
            ToolResult with TechnicalDocs data.
        """
        try:
            log.info("docs_analysis_started", product=product_name)

            # Search for documentation
            sources = []
            queries = [
                f"{product_name} API documentation model card",
                f"{product_name} rate limits authentication",
                f"{product_name} SDK examples quickstart",
            ]

            all_results = []
            for query in queries:
                results = await self.web_search.search(query, max_results=3)
                all_results.extend(results)
                sources.extend(r.url for r in results if r.url)

            # Deduplicate sources
            sources = list(set(sources))

            if not all_results:
                log.info("no_docs_found", product=product_name)
                return ToolResult.ok(data=TechnicalDocs.empty(), sources=[])

            # Extract docs info using LLM
            docs = await self._extract_docs(product_name, all_results)

            return ToolResult.ok(data=docs, sources=sources)

        except Exception as exc:
            log.error("docs_analysis_failed", error=str(exc))
            return ToolResult.fail(str(exc))

    async def _extract_docs(
        self,
        product_name: str,
        search_results: list,
    ) -> TechnicalDocs:
        """Extract documentation info using LLM."""
        try:
            # Format search results
            results_text = "\n\n".join(
                f"Source: {r.url}\nTitle: {r.title}\nContent: {r.snippet}"
                for r in search_results[:6]
            )

            message = await self.llm_client.messages.create(
                model=os.environ.get("LLM_MODEL", "qwen-max"),
                max_tokens=2048,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": DOCS_PROMPT.format(
                            product=product_name,
                            search_results=results_text,
                        ),
                    }
                ],
            )

            content = self._extract_text(message)
            data = json.loads(content)

            return TechnicalDocs(
                model_cards=data.get("model_cards", []),
                api_endpoints=data.get("api_endpoints", []),
                sdk_examples=data.get("sdk_examples", {}),
                rate_limits=data.get("rate_limits", {}),
            )

        except Exception as exc:
            log.warning("docs_extraction_failed", error=str(exc))
            return TechnicalDocs.empty()

    def _extract_text(self, message) -> str:
        """Extract text content from LLM response."""
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return str(message.content[0]) if message.content else ""