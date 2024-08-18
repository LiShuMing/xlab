"""Research Agent orchestrator - coordinates tools and synthesizes results."""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from .types import ResearchOptions, ResearchReport, ToolResult

if TYPE_CHECKING:
    from .tools.base_report import BaseReportTool
    from .tools.fact_verify import FactVerifyTool
    from .tools.competition import CompetitionTool
    from .tools.history import HistoryTool
    from .tools.docs_analyzer import DocsAnalyzerTool

load_dotenv(Path.home() / ".env")
load_dotenv(override=True)

log = structlog.get_logger()

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class ToolRegistry:
    """Registry of available research tools."""

    base_report: "BaseReportTool"
    fact_verify: "FactVerifyTool | None" = None
    competition: "CompetitionTool | None" = None
    history: "HistoryTool | None" = None
    docs_analyzer: "DocsAnalyzerTool | None" = None


class ResearchAgent:
    """Orchestrates research tools and synthesizes final reports."""

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def research(
        self,
        product_name: str,
        options: ResearchOptions | None = None,
    ) -> ResearchReport:
        """Generate a research report using the configured tools.

        Args:
            product_name: Name of the LLM API product to research.
            options: Research options. Defaults to deep mode with all tools.

        Returns:
            ResearchReport with synthesized findings.
        """
        if options is None:
            options = ResearchOptions()

        tools_used: list[str] = []
        sources: list[str] = []

        # 1. Generate base report (always runs)
        log.info("research_started", product=product_name, mode=options.mode.value)
        base_result = await self.tools.base_report.run(product_name, options)

        if not base_result.success:
            return ResearchReport(
                product_name=product_name,
                research_mode=options.mode,
                tools_used=[],
                sources=[],
            )

        tools_used.append("base_report")
        report = base_result.data

        # 2. Run intelligence tools in parallel
        tasks: dict[str, Any] = {}

        if (
            options.enable_fact_verify
            and self.tools.fact_verify is not None
        ):
            tasks["facts"] = self.tools.fact_verify.run(report, options)

        if (
            options.enable_competition
            and self.tools.competition is not None
        ):
            tasks["competition"] = self.tools.competition.run(
                product_name, options.competitors, options
            )

        if (
            options.enable_history
            and self.tools.history is not None
        ):
            tasks["history"] = self.tools.history.run(product_name, options)

        if (
            options.enable_docs_analysis
            and self.tools.docs_analyzer is not None
        ):
            tasks["docs"] = self.tools.docs_analyzer.run(product_name, options)

        # Execute tools in parallel
        if tasks:
            results = await asyncio.gather(
                *tasks.values(), return_exceptions=True
            )

            for name, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    log.warning(f"tool_{name}_failed", error=str(result))
                    continue
                if isinstance(result, ToolResult) and result.success:
                    tools_used.append(name)
                    sources.extend(result.sources)

                    # Attach result data to report
                    if name == "facts" and result.data:
                        report.verified_facts = result.data
                    elif name == "competition" and result.data:
                        report.competitive_insights = result.data
                    elif name == "history" and result.data:
                        report.version_history = result.data
                    elif name == "docs" and result.data:
                        report.technical_docs = result.data

        # 3. Update report metadata
        report.tools_used = tools_used
        report.sources = list(set(sources))
        report.research_mode = options.mode

        log.info(
            "research_completed",
            product=product_name,
            tools_used=tools_used,
            sources_count=len(sources),
        )

        return report

    @classmethod
    def create_default(
        cls,
        timeout: float = 120.0,
        enable_fact_verify: bool = True,
        enable_competition: bool = True,
        enable_history: bool = True,
        enable_docs_analysis: bool = True,
    ) -> "ResearchAgent":
        """Create a ResearchAgent with default configuration.

        Args:
            timeout: Timeout for LLM API calls.
            enable_fact_verify: Whether to enable fact verification tool.
            enable_competition: Whether to enable competition analysis tool.
            enable_history: Whether to enable version history tool.
            enable_docs_analysis: Whether to enable docs analyzer tool.

        Returns:
            Configured ResearchAgent instance.
        """
        from .tools.base_report import BaseReportTool
        from .tools.fact_verify import FactVerifyTool
        from .tools.competition import CompetitionTool
        from .tools.history import HistoryTool
        from .tools.docs_analyzer import DocsAnalyzerTool
        from .web_search import create_web_search_client

        base_report = BaseReportTool(timeout=timeout)

        # Create shared LLM client for tools that need it
        api_key = os.environ.get("LLM_API_KEY", "") or os.environ.get(
            "ANTHROPIC_API_KEY", ""
        )
        base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)

        llm_client: AsyncAnthropic | None = None
        fact_verify: FactVerifyTool | None = None
        competition: CompetitionTool | None = None
        history: HistoryTool | None = None
        docs_analyzer: DocsAnalyzerTool | None = None

        if api_key:
            llm_client = AsyncAnthropic(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
            web_search = create_web_search_client()

            if enable_fact_verify:
                fact_verify = FactVerifyTool(llm_client, web_search)

            if enable_competition:
                competition = CompetitionTool(llm_client, web_search)

            if enable_history:
                history = HistoryTool(llm_client, web_search)

            if enable_docs_analysis:
                docs_analyzer = DocsAnalyzerTool(llm_client, web_search)

        tools = ToolRegistry(
            base_report=base_report,
            fact_verify=fact_verify,
            competition=competition,
            history=history,
            docs_analyzer=docs_analyzer,
        )
        return cls(tools)