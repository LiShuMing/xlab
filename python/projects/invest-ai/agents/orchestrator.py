"""Agent orchestrator implementing ReAct pattern with LangGraph."""

import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated

from core.llm import LLMClient, LLMConfig
from core.logger import get_logger
from agents.base import AgentState, ToolResult

logger = get_logger(__name__)


class LangGraphState(TypedDict):
    """LangGraph state definition.

    Attributes:
        messages: Accumulated messages.
        tool_calls: Tool call history.
        tool_results: Tool execution results.
        step_count: Current step count.
    """

    messages: Annotated[list, add_messages]
    tool_calls: list[dict]
    tool_results: list[str]
    step_count: int


class AgentOrchestrator:
    """Agent orchestrator using LangGraph for ReAct pattern.

    This orchestrator manages multi-step reasoning and tool execution
    for stock analysis tasks.
    """

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        """Initialize orchestrator.

        Args:
            llm_config: Optional LLM configuration.
        """
        self.llm_client = LLMClient(llm_config)
        self.tools = self._init_tools()
        self.graph = self._build_graph()

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

    def _get_system_prompt(self) -> str:
        """Get system prompt for the agent.

        Returns:
            System prompt string.
        """
        return """You are a professional stock investment analysis assistant.

Available tools:
- query_stock_price: Get real-time stock price
- query_kline_data: Get historical K-line data
- query_financial_metrics: Get financial metrics
- query_market_news: Get market news

Your task is to:
1. Get the stock's real-time price
2. Get K-line data to understand recent trends
3. Get financial metrics to assess company quality
4. Get relevant news for market sentiment
5. Generate comprehensive investment recommendations

Call one tool at a time and decide the next step based on results."""

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow.

        Returns:
            Compiled StateGraph.
        """
        builder = StateGraph(LangGraphState)

        builder.add_node("agent", self._agent_node)
        builder.add_node("tool_executor", self._tool_executor)

        builder.set_entry_point("agent")

        builder.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tool_executor",
                "end": END,
            },
        )
        builder.add_edge("tool_executor", "agent")

        return builder.compile()

    def _agent_node(self, state: LangGraphState) -> dict:
        """Agent node for LLM reasoning.

        Args:
            state: Current state.

        Returns:
            State updates.
        """
        messages = state["messages"]
        response = self.llm_client.model.invoke(messages)

        return {
            "messages": [response],
            "step_count": state.get("step_count", 0) + 1,
        }

    def _tool_executor(self, state: LangGraphState) -> dict:
        """Tool executor node.

        Args:
            state: Current state.

        Returns:
            State updates with tool results.
        """
        last_message = state["messages"][-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"tool_results": state.get("tool_results", [])}

        tool_results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            tool = self._find_tool(tool_name)
            if tool:
                import asyncio

                result = asyncio.run(tool.execute(tool_args))
                tool_results.append(result)
            else:
                tool_results.append(f"Tool {tool_name} not found")

        return {
            "tool_results": tool_results,
            "messages": [AIMessage(content="\n".join(tool_results))],
        }

    def _find_tool(self, name: str) -> Optional[Any]:
        """Find tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool instance or None.
        """
        for tool in self.tools:
            if tool.name == name or tool.get_info().name == name:
                return tool
        return None

    def _should_continue(self, state: LangGraphState) -> str:
        """Determine if execution should continue.

        Args:
            state: Current state.

        Returns:
            'continue' or 'end'.
        """
        if state.get("step_count", 0) >= 10:
            return "end"

        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"

        return "end"

    async def analyze(self, stock_code: str, user_query: str) -> AgentState:
        """Execute stock analysis.

        Args:
            stock_code: Stock code to analyze.
            user_query: User's analysis request.

        Returns:
            AgentState with results.
        """
        start_time = time.time()
        state = AgentState()

        try:
            system_prompt = self._get_system_prompt()
            initial_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Please analyze stock {stock_code}. {user_query}"),
            ]

            langgraph_state = LangGraphState(
                messages=initial_messages,
                tool_calls=[],
                tool_results=[],
                step_count=0,
            )

            final_state = self.graph.invoke(langgraph_state)

            state.is_complete = True
            state.final_response = final_state["messages"][-1].content

            return state

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return state.fail(str(e))


class SimpleAgentOrchestrator:
    """Simplified agent orchestrator without LangGraph dependency.

    This orchestrator executes tools sequentially for straightforward
    analysis workflows.
    """

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        """Initialize simplified orchestrator.

        Args:
            llm_config: Optional LLM configuration.
        """
        self.llm_client = LLMClient(llm_config)
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
        state = AgentState()
        state.add_message("user", f"Please analyze stock {stock_code}. {user_query}")

        collected_data = {}

        try:
            tool_order = [
                ("query_stock_price", {"stock_code": stock_code}),
                ("query_kline_data", {"stock_code": stock_code, "days": 30}),
                ("query_financial_metrics", {"stock_code": stock_code}),
                ("query_market_news", {"stock_code": stock_code, "limit": 5}),
            ]

            for tool_name, args in tool_order:
                tool = self._find_tool(tool_name)
                if tool:
                    result = await tool.execute(args)
                    collected_data[tool_name] = result
                    state.add_message("assistant", f"Collected {tool_name} data")

            report = await self._generate_report(stock_code, collected_data)
            state.complete(report)

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

    async def _generate_report(self, stock_code: str, data: dict) -> str:
        """Generate analysis report.

        Args:
            stock_code: Stock code.
            data: Collected tool data.

        Returns:
            Formatted report string.
        """
        import time

        report = f"# {stock_code} Investment Analysis Report\n\n"
        report += f"**Generated**: {time.strftime('%Y-%m-%d %H:%M')}\n\n"

        if "query_stock_price" in data:
            report += "## Real-Time Price\n\n"
            report += data["query_stock_price"]
            report += "\n\n"

        if "query_kline_data" in data:
            report += "## K-Line Trend\n\n"
            report += data["query_kline_data"]
            report += "\n\n"

        if "query_financial_metrics" in data:
            report += "## Financial Metrics\n\n"
            report += data["query_financial_metrics"]
            report += "\n\n"

        if "query_market_news" in data:
            report += "## Market News\n\n"
            report += data["query_market_news"]

        return report
