"""Agent 编排器 - 基于 LangGraph 的 ReAct 模式实现"""

import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated

from core.llm import LLMClient, LLMConfig
from core.logger import get_logger
from agents.base import AgentState, ToolResult
from agents.tools import (
    QueryStockPriceTool,
    QueryKLineDataTool,
    QueryFinancialMetricsTool,
    QueryMarketNewsTool,
)

logger = get_logger(__name__)


class LangGraphState(TypedDict):
    """LangGraph 状态"""

    messages: Annotated[list, add_messages]
    tool_calls: list[dict]
    tool_results: list[str]
    step_count: int


class AgentOrchestrator:
    """Agent 编排器 - 基于 LangGraph 实现 ReAct 模式"""

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm_client = LLMClient(llm_config)
        self.tools = self._init_tools()
        self.graph = self._build_graph()

    def _init_tools(self) -> list:
        """初始化工具列表"""
        return [
            QueryStockPriceTool(),
            QueryKLineDataTool(),
            QueryFinancialMetricsTool(),
            QueryMarketNewsTool(),
        ]

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的股票投资分析助手。你可以通过调用工具来获取股票价格、K 线数据、财务指标和市场新闻。

你的任务是通过调用适当的工具，收集全面的股票信息，然后生成一份专业的投资分析报告。

可用工具：
- query_stock_price: 查询股票实时价格
- query_kline_data: 查询股票 K 线数据（历史走势）
- query_financial_metrics: 查询财务指标（估值、盈利能力等）
- query_market_news: 查询市场新闻

请按照以下步骤进行分析：
1. 首先获取股票的实时价格
2. 获取 K 线数据了解近期走势
3. 获取财务指标评估公司质量
4. 获取相关新闻了解市场情绪
5. 综合所有信息生成投资建议

每次只调用一个工具，根据工具返回结果决定下一步行动。"""

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流"""
        builder = StateGraph(LangGraphState)

        # 添加节点
        builder.add_node("agent", self._agent_node)
        builder.add_node("tool_executor", self._tool_executor)

        # 设置入口
        builder.set_entry_point("agent")

        # 添加边
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
        """Agent 节点 - LLM 思考和决策"""
        messages = state["messages"]

        # 调用 LLM
        response = self.llm_client.model.invoke(messages)

        return {
            "messages": [response],
            "step_count": state.get("step_count", 0) + 1,
        }

    def _tool_executor(self, state: LangGraphState) -> dict:
        """工具执行节点"""
        last_message = state["messages"][-1]

        # 解析工具调用
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"tool_results": state.get("tool_results", [])}

        tool_results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            # 查找并执行工具
            tool = self._find_tool(tool_name)
            if tool:
                import asyncio

                result = asyncio.run(tool.execute(tool_args))
                tool_results.append(result)
            else:
                tool_results.append(f"工具 {tool_name} 不存在")

        return {
            "tool_results": tool_results,
            "messages": [AIMessage(content="\n".join(tool_results))],
        }

    def _find_tool(self, name: str) -> Optional[Any]:
        """查找工具"""
        for tool in self.tools:
            if tool.name == name or tool.get_info().name == name:
                return tool
        return None

    def _should_continue(self, state: LangGraphState) -> str:
        """判断是否继续执行"""
        # 检查最大步数
        if state.get("step_count", 0) >= 10:
            return "end"

        # 检查是否有工具调用
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"

        return "end"

    async def analyze(self, stock_code: str, user_query: str) -> AgentState:
        """执行股票分析"""
        start_time = time.time()
        state = AgentState()

        try:
            # 初始化消息
            system_prompt = self._get_system_prompt()
            initial_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"请分析股票 {stock_code}。{user_query}"),
            ]

            # 转换为 LangGraph 状态
            langgraph_state = LangGraphState(
                messages=initial_messages,
                tool_calls=[],
                tool_results=[],
                step_count=0,
            )

            # 执行工作流
            final_state = self.graph.invoke(langgraph_state)

            # 构建 AgentState
            state.is_complete = True
            state.final_response = final_state["messages"][-1].content

            return state

        except Exception as e:
            logger.error(f"分析失败：{e}")
            return state.fail(str(e))


class SimpleAgentOrchestrator:
    """简化版 Agent 编排器 - 不依赖 LangGraph"""

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm_client = LLMClient(llm_config)
        self.tools = self._init_tools()

    def _init_tools(self) -> list:
        """初始化工具列表"""
        return [
            QueryStockPriceTool(),
            QueryKLineDataTool(),
            QueryFinancialMetricsTool(),
            QueryMarketNewsTool(),
        ]

    def _get_tool_descriptions(self) -> str:
        """获取工具描述"""
        descriptions = []
        for tool in self.tools:
            info = tool.get_info()
            params = ", ".join([f"{p.name}({p.type})" for p in info.parameters])
            descriptions.append(f"- {info.name}({params}): {info.description}")
        return "\n".join(descriptions)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return f"""你是一个专业的股票投资分析助手。

可用工具：
{self._get_tool_descriptions()}

请以 JSON 格式返回工具调用，格式如下：
{{"tool": "工具名", "args": {{参数}}}}

如果要结束分析并生成报告，返回：
{{"done": true, "report": "你的分析报告"}}"""

    async def analyze(self, stock_code: str, user_query: str) -> AgentState:
        """执行股票分析 - 简化版本"""
        import json
        import re

        state = AgentState()
        state.add_message("user", f"请分析股票 {stock_code}。{user_query}")

        # 收集的数据
        collected_data = {}

        try:
            # 顺序调用各工具收集数据
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
                    state.add_message("assistant", f"已获取 {tool_name} 数据")

            # 生成最终报告
            report = await self._generate_report(stock_code, collected_data)
            state.complete(report)

        except Exception as e:
            state.fail(str(e))

        return state

    def _find_tool(self, name: str) -> Optional[Any]:
        """查找工具"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _generate_report(self, stock_code: str, data: dict) -> str:
        """生成分析报告"""
        report = f"# {stock_code} 投资分析报告\n\n"
        report += f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M')}\n\n"

        # 整合各工具数据
        if "query_stock_price" in data:
            report += "## 实时股价\n\n"
            report += data["query_stock_price"]
            report += "\n\n"

        if "query_kline_data" in data:
            report += "## K 线走势\n\n"
            report += data["query_kline_data"]
            report += "\n\n"

        if "query_financial_metrics" in data:
            report += "## 财务指标\n\n"
            report += data["query_financial_metrics"]
            report += "\n\n"

        if "query_market_news" in data:
            report += "## 市场新闻\n\n"
            report += data["query_market_news"]

        return report
