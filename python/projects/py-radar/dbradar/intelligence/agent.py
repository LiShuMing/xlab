"""Intelligence agent that orchestrates analysis tools."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Set

from dbradar.intelligence.competition import CompetitionAnalyzer
from dbradar.intelligence.trends import TrendAnalyzer
from dbradar.intelligence.types import (
    AnalysisMode,
    AnalysisOptions,
    CompetitiveInsight,
    IntelligenceReport,
    ToolResult,
    TrendResult,
)
from dbradar.summarizer import Summarizer, SummaryResult

if TYPE_CHECKING:
    from dbradar.config import Config
    from dbradar.ranker import RankedItem


@dataclass
class AnalysisContext:
    """Context passed between analysis stages."""

    summary_result: Optional[SummaryResult] = None
    trends_result: Optional[TrendResult] = None
    competition_result: List[CompetitiveInsight] = None
    tools_used: List[str] = None

    def __post_init__(self):
        if self.competition_result is None:
            self.competition_result = []
        if self.tools_used is None:
            self.tools_used = []


class IntelligenceAgent:
    """Orchestrates intelligence analysis tools."""

    def __init__(self, config: Optional[Config] = None):
        from dbradar.config import get_config

        self.config = config or get_config()
        self.summarizer = Summarizer(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
            language=self.config.language,
        )
        self.trend_analyzer = TrendAnalyzer(
            output_dir=self.config.output_dir,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
        )
        self.competition_analyzer = CompetitionAnalyzer(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
        )

    def analyze(
        self,
        items: List[RankedItem],
        options: AnalysisOptions,
    ) -> IntelligenceReport:
        """
        Run intelligence analysis on ranked items.

        Args:
            items: List of ranked items to analyze.
            options: Analysis options specifying which tools to run.

        Returns:
            IntelligenceReport with summary and optional intelligence data.
        """
        context = AnalysisContext()

        # Step 1: Core summary (always runs, must succeed)
        summary_result = self.summarizer.summarize(items, top_k=options.top_k)

        if not summary_result.executive_summary or summary_result.executive_summary[
            0
        ].startswith("Error"):
            return IntelligenceReport.error(
                summary_result.executive_summary[0]
                if summary_result.executive_summary
                else "Unknown error during summarization"
            )

        context.summary_result = summary_result
        context.tools_used.append("summarize")

        # Step 2: Run intelligence tools in parallel if enabled
        if options.enable_trends or options.enable_competition:
            self._run_parallel_analysis(context, options)

        # Step 3: Synthesize final report
        return IntelligenceReport(
            executive_summary=context.summary_result.executive_summary,
            top_updates=context.summary_result.top_updates,
            release_notes=context.summary_result.release_notes,
            themes=context.summary_result.themes,
            action_items=context.summary_result.action_items,
            trends=context.trends_result,
            competition=context.competition_result,
            analysis_mode=options.mode,
            tools_used=context.tools_used,
        )

    def _run_parallel_analysis(
        self,
        context: AnalysisContext,
        options: AnalysisOptions,
    ) -> None:
        """Run enabled analysis tools in parallel using ThreadPoolExecutor."""

        tasks = []

        # Prepare trend analysis task
        if options.enable_trends and self.trend_analyzer.has_history(days=options.history_days):
            tasks.append(("trends", self._run_trends_analysis, context.summary_result, options))

        # Prepare competition analysis task
        if options.enable_competition:
            products = {i.item.product for i in []}  # Will be extracted from summary
            tasks.append(("competition", self._run_competition_analysis, context.summary_result, products))

        if not tasks:
            return

        # Run tasks in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for name, func, *args in tasks:
                future = executor.submit(func, *args)
                futures[future] = name

            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if name == "trends":
                        if result.success:
                            context.trends_result = result.data
                            context.tools_used.append("trends")
                    elif name == "competition":
                        if result.success:
                            context.competition_result = result.data
                            context.tools_used.append("competition")
                except Exception:
                    # Graceful degradation: continue without failed tool
                    pass

    def _run_trends_analysis(
        self,
        summary: SummaryResult,
        options: AnalysisOptions,
    ) -> ToolResult:
        """Run trend analysis."""
        return self.trend_analyzer.analyze(summary, history_days=options.history_days)

    def _run_competition_analysis(
        self,
        summary: SummaryResult,
        products: Optional[Set[str]] = None,
    ) -> ToolResult:
        """Run competition analysis."""
        return self.competition_analyzer.analyze(summary, products=products)

    def close(self) -> None:
        """Close all HTTP clients."""
        self.summarizer.client.close()
        self.trend_analyzer.close()
        self.competition_analyzer.close()


def run_intelligence(
    items: List[RankedItem],
    mode: AnalysisMode = AnalysisMode.BASIC,
    top_k: int = 10,
    history_days: int = 14,
) -> IntelligenceReport:
    """
    Convenience function to run intelligence analysis.

    Args:
        items: List of ranked items to analyze.
        mode: Analysis mode (BASIC, TRENDS, COMPETITION, or INTELLIGENCE).
        top_k: Number of top items to include.
        history_days: Days of history for trend analysis.

    Returns:
        IntelligenceReport with analysis results.
    """
    options = AnalysisOptions(
        mode=mode,
        top_k=top_k,
        history_days=history_days,
        enable_trends=mode in (AnalysisMode.TRENDS, AnalysisMode.INTELLIGENCE),
        enable_competition=mode in (AnalysisMode.COMPETITION, AnalysisMode.INTELLIGENCE),
    )

    agent = IntelligenceAgent()
    try:
        return agent.analyze(items, options)
    finally:
        agent.close()