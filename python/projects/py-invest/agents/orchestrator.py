"""Agent orchestrator implementing ReAct pattern with LangGraph."""

import asyncio
import time
from typing import Any, Optional

from core.llm import LLMClient, LLMConfig, HumanMessage, AIMessage, SystemMessage, RateLimitedLLMClient
from core.logger import get_logger
from agents.base import AgentState, ToolResult
from modules.report_generator.types import Report
from modules.report_generator.formatter import ReportFormatter, ReportFormat

logger = get_logger(__name__)


class SimpleAgentOrchestrator:
    """Simplified agent orchestrator without LangGraph dependency.

    This orchestrator executes tools sequentially for straightforward
    analysis workflows.
    """

    def __init__(self, llm_config: Optional[LLMConfig] = None, lang: str = "zh"):
        """Initialize simplified orchestrator.

        Args:
            llm_config: Optional LLM configuration.
            lang: Output language ("zh" for Chinese, "en" for English).
        """
        base_client = LLMClient(llm_config)
        # Wrap with rate limiting to prevent timeout during parallel agent execution
        # Allow 4 concurrent calls for parallel specialist agents
        self.llm_client = RateLimitedLLMClient.wrap(base_client, max_concurrent=4)
        self.lang = lang
        self.tools = self._init_tools()

    def _init_tools(self) -> list:
        """Initialize available tools.

        Returns:
            List of tool instances.
        """
        from agents.tools import (
            QueryStockPriceTool,
            QueryKLineDataTool,
            QueryFinancialMetricsTool,
            QueryMarketNewsTool,
        )
        return [
            QueryStockPriceTool(),
            QueryKLineDataTool(),
            QueryFinancialMetricsTool(),
            QueryMarketNewsTool(),
        ]

    def _get_tool_descriptions(self) -> str:
        """Get tool descriptions.

        Returns:
            Formatted tool descriptions string.
        """
        descriptions = []
        for tool in self.tools:
            info = tool.get_info()
            params = ", ".join([f"{p.name}({p.type})" for p in info.parameters])
            descriptions.append(f"- {info.name}({params}): {info.description}")
        return "\n".join(descriptions)

    def _get_system_prompt(self) -> str:
        """Get system prompt.

        Returns:
            System prompt string.
        """
        return f"""You are a professional stock investment analysis assistant.

Available tools:
{self._get_tool_descriptions()}

Analyze the stock thoroughly and provide investment recommendations."""

    async def analyze(self, stock_code: str, user_query: str) -> AgentState:
        """Execute stock analysis.

        Args:
            stock_code: Stock code.
            user_query: User's request.

        Returns:
            AgentState with results.
        """
        start_time = time.time()
        state = AgentState()
        state.add_message("user", f"Please analyze stock {stock_code}. {user_query}")

        collected_data = {}

        try:
            # Collect data in parallel for better performance
            tool_calls = [
                ("query_stock_price", {"stock_code": stock_code}),
                ("query_kline_data", {"stock_code": stock_code, "days": 30}),
                ("query_financial_metrics", {"stock_code": stock_code}),
                ("query_market_news", {"stock_code": stock_code, "limit": 5}),
            ]

            # Execute all tools in parallel
            async def execute_tool(tool_name: str, args: dict):
                tool = self._find_tool(tool_name)
                if tool:
                    result = await tool.execute(args)
                    # ToolResult object with metadata containing raw_data
                    return tool_name, result
                return tool_name, None

            results = await asyncio.gather(
                *[execute_tool(name, args) for name, args in tool_calls]
            )

            for tool_name, result in results:
                if result and hasattr(result, 'success') and result.success:
                    # Store both the markdown result and raw_data from metadata
                    collected_data[tool_name] = result
                    state.add_message("assistant", f"Collected {tool_name} data")
                elif result:
                    # Store failed result too
                    collected_data[tool_name] = result

            logger.info(f"Data collection completed in {time.time() - start_time:.2f}s")

            report = await self._generate_report(stock_code, collected_data)
            state.report = report
            state.complete(ReportFormatter.format(report, ReportFormat.MARKDOWN))

            logger.info(f"Total analysis completed in {time.time() - start_time:.2f}s")

        except Exception as e:
            state.fail(str(e))

        return state

    def _find_tool(self, name: str) -> Optional[Any]:
        """Find tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool instance or None.
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _generate_report(self, stock_code: str, data: dict) -> Report:
        """Generate analysis report using multi-agent pipeline.

        Args:
            stock_code: Stock code.
            data: Collected tool data.

        Returns:
            Report object.
        """
        from agents.specialist_agents import (
            TechnicalAnalystAgent,
            FundamentalAnalystAgent,
            RiskOfficerAgent,
            SectorStrategistAgent,
        )
        from agents.synthesis_agent import SynthesisAgent

        llm = self.llm_client

        # Run four specialist agents in parallel
        start = time.time()
        logger.info("Starting parallel specialist analysis...")

        async def timed_analyze(agent_cls, name):
            t0 = time.time()
            result = await agent_cls(stock_code, llm).analyze(data)
            logger.info(f"{name} completed in {time.time() - t0:.1f}s")
            return result

        results = await asyncio.gather(
            timed_analyze(TechnicalAnalystAgent, "TechnicalAgent"),
            timed_analyze(FundamentalAnalystAgent, "FundamentalAgent"),
            timed_analyze(RiskOfficerAgent, "RiskAgent"),
            timed_analyze(SectorStrategistAgent, "SectorAgent"),
            return_exceptions=True,
        )

        logger.info(f"All specialists completed in {time.time() - start:.1f}s")

        # Handle exceptions with defaults
        from agents.specialist_agents import (
            TechnicalOutput,
            FundamentalOutput,
            RiskOutput,
            SectorOutput,
        )

        tech = results[0] if not isinstance(results[0], Exception) else TechnicalOutput()
        fund = results[1] if not isinstance(results[1], Exception) else FundamentalOutput()
        risk = results[2] if not isinstance(results[2], Exception) else RiskOutput()
        sector = results[3] if not isinstance(results[3], Exception) else await SectorOutput.with_llm_fallback(stock_code, llm)

        # Synthesize into final report
        t0 = time.time()
        report = await SynthesisAgent(stock_code, llm, lang=self.lang).synthesize(tech, fund, risk, sector, data)
        logger.info(f"Synthesis completed in {time.time() - t0:.1f}s")

        return report
