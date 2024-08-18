"""Agent orchestrator implementing ReAct pattern with LangGraph."""

import asyncio
import os
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

    async def analyze(self, stock_code: str, user_query: str, mode: str = "deep") -> AgentState:
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

        mode = mode if mode in {"fast", "deep"} else "deep"

        try:
            collected_data = await self.collect_data(stock_code)
            for tool_name, result in collected_data.items():
                if result and getattr(result, "success", False):
                    state.add_message("assistant", f"Collected {tool_name} data")
                elif result:
                    state.add_message("assistant", f"{tool_name} failed: {result.error}")

            logger.info(f"Data collection completed in {time.time() - start_time:.2f}s")

            if mode == "fast":
                report = await self._generate_fast_report(stock_code, collected_data, user_query)
            else:
                report = await self._generate_report(stock_code, collected_data)
            report.analysis_duration = time.time() - start_time
            state.report = report
            state.complete(ReportFormatter.format(report, ReportFormat.MARKDOWN))

            logger.info(f"Total analysis completed in {time.time() - start_time:.2f}s")

        except Exception as e:
            state.fail(str(e))

        return state

    async def collect_data(self, stock_code: str) -> dict[str, ToolResult]:
        """Collect all market data concurrently with per-tool timeouts."""
        tool_timeout = int(os.getenv("PY_INVEST_TOOL_TIMEOUT", "20"))
        tool_calls = [
            ("query_stock_price", {"stock_code": stock_code}),
            ("query_kline_data", {"stock_code": stock_code, "days": 30}),
            ("query_financial_metrics", {"stock_code": stock_code}),
            ("query_market_news", {"stock_code": stock_code, "limit": 5}),
        ]

        async def execute_tool(tool_name: str, args: dict):
            tool = self._find_tool(tool_name)
            if not tool:
                return tool_name, ToolResult.fail("Tool not found", tool_name)
            try:
                result = await asyncio.wait_for(tool.execute(args), timeout=tool_timeout)
                return tool_name, result
            except asyncio.TimeoutError:
                return tool_name, ToolResult.fail(f"Timed out after {tool_timeout}s", tool_name)
            except Exception as exc:
                return tool_name, ToolResult.fail(str(exc), tool_name)

        results = await asyncio.gather(*[execute_tool(name, args) for name, args in tool_calls])
        return {tool_name: result for tool_name, result in results if result is not None}

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

        deep_config = LLMConfig.from_env()
        deep_config.max_tokens = int(os.getenv("PY_INVEST_DEEP_MAX_TOKENS", "6500"))
        deep_config.temperature = float(os.getenv("PY_INVEST_DEEP_TEMPERATURE", "0.25"))
        llm = RateLimitedLLMClient.wrap(LLMClient(deep_config), max_concurrent=4)

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
        deep_synthesis_config = LLMConfig.from_env()
        deep_synthesis_config.max_tokens = int(os.getenv("PY_INVEST_DEEP_SYNTHESIS_MAX_TOKENS", "9000"))
        deep_synthesis_config.temperature = float(os.getenv("PY_INVEST_DEEP_SYNTHESIS_TEMPERATURE", "0.22"))
        deep_synthesis_llm = RateLimitedLLMClient.wrap(LLMClient(deep_synthesis_config), max_concurrent=1)
        synthesis_agent = SynthesisAgent(stock_code, deep_synthesis_llm, lang=self.lang)
        synthesis_timeout = int(os.getenv("PY_INVEST_SYNTHESIS_TIMEOUT", "210"))
        try:
            report = await asyncio.wait_for(
                synthesis_agent.synthesize(tech, fund, risk, sector, data),
                timeout=synthesis_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Synthesis timed out after {synthesis_timeout}s; using fallback report")
            price_data = synthesis_agent._extract_price_data(data)
            report_data = synthesis_agent._get_default_report_data(price_data)
            report_data.update({
                "technical_analysis": (
                    f"趋势：{tech.trend}；支撑位：{tech.support or '数据待补充'}；"
                    f"压力位：{tech.resistance or '数据待补充'}；动量评分：{tech.momentum_score}/10。"
                    f"{tech.near_term_outlook}"
                ),
                "financial_health": (
                    f"估值判断：{fund.valuation}；质量评分：{fund.quality_score}/10；"
                    f"P/E：{fund.pe_ratio or '数据待补充'}；P/B：{fund.pb_ratio or '数据待补充'}。"
                    f"{fund.key_metric_comment}"
                ),
                "macro_sector": (
                    f"行业：{sector.sector or '数据待补充'}；竞争位置：{sector.positioning}。"
                    f"顺风因素：{sector.tailwinds or '数据待补充'}；逆风因素：{sector.headwinds or '数据待补充'}。"
                ),
                "risk_matrix": "\n".join(
                    f"- {item.description}（概率：{item.probability}，影响：{item.impact}）"
                    for item in risk.risks
                ) or "风险数据待补充",
                "summary": "最终综合生成超时，以下为基于各 specialist agent 输出的快速 fallback 报告。",
            })
            report = synthesis_agent._build_report(report_data, tech, fund, risk, sector, data, price_data)
        logger.info(f"Synthesis completed in {time.time() - t0:.1f}s")

        return report

    async def _generate_fast_report(self, stock_code: str, data: dict, user_query: str) -> Report:
        """Generate a one-pass report optimized for interactive latency."""
        from agents.synthesis_agent import SynthesisAgent
        from agents.specialist_agents import TechnicalOutput, FundamentalOutput, RiskOutput, SectorOutput

        t0 = time.time()
        timeout = int(os.getenv("PY_INVEST_FAST_TIMEOUT", "120"))
        fast_config = LLMConfig.from_env()
        fast_config.max_tokens = int(os.getenv("PY_INVEST_FAST_MAX_TOKENS", "2200"))
        fast_config.temperature = float(os.getenv("PY_INVEST_FAST_TEMPERATURE", "0.2"))
        fast_llm = RateLimitedLLMClient.wrap(LLMClient(fast_config), max_concurrent=1)
        synthesis_agent = SynthesisAgent(stock_code, fast_llm, lang=self.lang)
        try:
            report = await asyncio.wait_for(
                synthesis_agent.synthesize_fast(data, user_query),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Fast report timed out after {timeout}s; using deterministic fallback")
            price_data = synthesis_agent._extract_price_data(data)
            report_data = synthesis_agent._get_default_report_data(price_data)
            report_data["summary"] = "快速分析超时，以下为基于已采集数据生成的保守框架。"
            report = synthesis_agent._build_report(
                report_data,
                TechnicalOutput(),
                FundamentalOutput(),
                RiskOutput(),
                SectorOutput(),
                data,
                price_data,
            )
        logger.info(f"Fast report completed in {time.time() - t0:.1f}s")
        return report
