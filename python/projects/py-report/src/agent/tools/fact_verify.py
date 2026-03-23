"""Fact verification tool - verifies claims via web search and LLM analysis."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from ..types import ResearchOptions, ResearchReport, ToolResult, VerifiedFact
from ..web_search import WebSearchClient, create_web_search_client

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Prompt for extracting verifiable claims from a report
CLAIM_EXTRACTION_PROMPT = """\
You are a fact-checking assistant. Extract the most important verifiable claims from the following research report.

Focus on:
1. Pricing claims (token costs, tier pricing)
2. Performance claims (latency, throughput benchmarks)
3. Feature claims (context window size, capabilities)
4. Version/release claims (dates, version numbers)

Return a JSON array of objects with:
- claim: The specific claim (be precise)
- category: One of "pricing", "performance", "feature", "version", "other"
- importance: "high", "medium", or "low" based on how central this claim is to the report

Report:
{report_content}

Return ONLY the JSON array, no other text. Maximum 10 claims.
"""

# Prompt for verifying a claim against search results
VERIFICATION_PROMPT = """\
You are a fact-checking assistant. Verify the following claim against the provided search results.

Claim: {claim}

Search Results:
{search_results}

Determine:
1. Is the claim verified, partially verified, contradicted, or not found?
2. What is your confidence level (0.0-1.0)?
3. Which source best supports your conclusion?

Return a JSON object with:
- status: "verified", "partial", "contradicted", or "unfound"
- confidence: float between 0.0 and 1.0
- best_source_url: the URL of the most relevant source
- best_source_snippet: the relevant text from that source
- reasoning: one sentence explaining your conclusion

Return ONLY the JSON object, no other text.
"""


@dataclass
class ExtractedClaim:
    """A claim extracted from a report for verification."""

    claim: str
    category: str
    importance: str


class FactVerifyTool:
    """Tool for verifying claims in a research report via web search."""

    def __init__(
        self,
        llm_client,  # AsyncAnthropic client
        web_search: WebSearchClient | None = None,
        max_claims: int = 10,
    ):
        self.llm_client = llm_client
        self.web_search = web_search or create_web_search_client()
        self.max_claims = max_claims

    async def run(
        self,
        report: ResearchReport,
        options: ResearchOptions | None = None,
    ) -> ToolResult:
        """Verify claims in the report.

        Args:
            report: The research report to verify.
            options: Research options (unused for now).

        Returns:
            ToolResult with list of VerifiedFact objects.
        """
        try:
            # 1. Extract claims from the report
            claims = await self._extract_claims(report.raw_markdown)
            if not claims:
                log.info("no_claims_extracted")
                return ToolResult.ok(data=[], sources=[])

            log.info("claims_extracted", count=len(claims))

            # 2. Verify each claim
            verified_facts: list[VerifiedFact] = []
            sources: list[str] = []

            for claim in claims[: self.max_claims]:
                # Search for evidence
                search_results = await self.web_search.search(claim.claim, max_results=3)

                if not search_results:
                    verified_facts.append(
                        VerifiedFact(
                            claim=claim.claim,
                            source_url="",
                            source_snippet="",
                            verification_status="unfound",
                            confidence=0.0,
                        )
                    )
                    continue

                # Verify using LLM
                result = await self._verify_claim(claim.claim, search_results)

                if result:
                    verified_facts.append(result)
                    if result.source_url:
                        sources.append(result.source_url)

            log.info(
                "facts_verified",
                total=len(verified_facts),
                verified=sum(1 for f in verified_facts if f.verification_status == "verified"),
            )

            return ToolResult.ok(data=verified_facts, sources=sources)

        except Exception as exc:
            log.error("fact_verify_failed", error=str(exc))
            return ToolResult.fail(str(exc))

    async def _extract_claims(self, markdown: str) -> list[ExtractedClaim]:
        """Extract verifiable claims from markdown content."""
        try:
            # Use the LLM to extract claims
            message = await self.llm_client.messages.create(
                model=os.environ.get("LLM_MODEL", "qwen-max"),
                max_tokens=2048,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": CLAIM_EXTRACTION_PROMPT.format(
                            report_content=markdown[:8000]  # Truncate if too long
                        ),
                    }
                ],
            )

            content = self._extract_text(message)

            # Parse JSON response
            claims_data = json.loads(content)
            return [
                ExtractedClaim(
                    claim=c.get("claim", ""),
                    category=c.get("category", "other"),
                    importance=c.get("importance", "medium"),
                )
                for c in claims_data
                if c.get("claim")
            ]

        except Exception as exc:
            log.warning("claim_extraction_failed", error=str(exc))
            return []

    async def _verify_claim(
        self,
        claim: str,
        search_results: list,
    ) -> VerifiedFact | None:
        """Verify a single claim against search results."""
        try:
            # Format search results for prompt
            results_text = "\n\n".join(
                f"Source: {r.url}\nTitle: {r.title}\nContent: {r.snippet}"
                for r in search_results
            )

            message = await self.llm_client.messages.create(
                model=os.environ.get("LLM_MODEL", "qwen-max"),
                max_tokens=512,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": VERIFICATION_PROMPT.format(
                            claim=claim,
                            search_results=results_text,
                        ),
                    }
                ],
            )

            content = self._extract_text(message)
            result = json.loads(content)

            return VerifiedFact(
                claim=claim,
                source_url=result.get("best_source_url", ""),
                source_snippet=result.get("best_source_snippet", ""),
                verification_status=result.get("status", "unfound"),
                confidence=result.get("confidence", 0.0),
            )

        except Exception as exc:
            log.warning("claim_verification_failed", claim=claim[:50], error=str(exc))
            return None

    def _extract_text(self, message) -> str:
        """Extract text content from LLM response."""
        for block in message.content:
            if hasattr(block, "text"):
                return block.text
        return str(message.content[0]) if message.content else ""