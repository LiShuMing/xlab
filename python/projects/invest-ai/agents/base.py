"""Agent 系统 - 基于 ReAct 模式的多 Agent 编排"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class ToolParameter:
    """工具参数定义"""

    name: str
    type: str  # string, number, integer, boolean, array, object
    description: str
    required: bool = False
    enum: Optional[list] = None
    default: Optional[Any] = None


@dataclass
class ToolInfo:
    """工具元信息"""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)


class BaseAgentTool(ABC):
    """Agent 工具基类"""

    name: str = "base_tool"
    description: str = "基础工具"

    @abstractmethod
    def get_info(self) -> ToolInfo:
        """获取工具信息，供 LLM 理解工具用途"""
        pass

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """执行工具逻辑，返回字符串结果"""
        pass

    def validate_params(self, params: dict[str, Any]) -> bool:
        """参数校验"""
        info = self.get_info()
        for param in info.parameters:
            if param.required and param.name not in params:
                return False
        return True

    def get_schema(self) -> dict:
        """获取 JSON Schema 格式的工具描述"""
        info = self.get_info()
        properties = {}
        required = []

        for param in info.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "name": info.name,
            "description": info.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    result: str = ""
    error: Optional[str] = None
    tool_name: str = ""
    execution_time: float = 0.0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, result: str, tool_name: str = "", metadata: dict = None) -> "ToolResult":
        return cls(
            success=True,
            result=result,
            tool_name=tool_name,
            metadata=metadata or {},
        )

    @classmethod
    def fail(cls, error: str, tool_name: str = "") -> "ToolResult":
        return cls(
            success=False,
            error=error,
            tool_name=tool_name,
        )


@dataclass
class AgentState:
    """Agent 执行状态"""

    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    is_complete: bool = False
    final_response: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str) -> "AgentState":
        """添加消息"""
        self.messages.append({"role": role, "content": content, "timestamp": datetime.now()})
        self.updated_at = datetime.now()
        return self

    def add_tool_call(self, tool_name: str, args: dict) -> "AgentState":
        """添加工具调用"""
        self.tool_calls.append(
            {"tool_name": tool_name, "args": args, "timestamp": datetime.now()}
        )
        self.updated_at = datetime.now()
        return self

    def add_tool_result(self, result: ToolResult) -> "AgentState":
        """添加工具执行结果"""
        self.tool_results.append(result)
        self.updated_at = datetime.now()
        return self

    def next_step(self) -> int:
        """进入下一步"""
        self.current_step += 1
        self.updated_at = datetime.now()
        return self.current_step

    def complete(self, response: str) -> "AgentState":
        """标记完成"""
        self.is_complete = True
        self.final_response = response
        self.updated_at = datetime.now()
        return self

    def fail(self, error: str) -> "AgentState":
        """标记失败"""
        self.error = error
        self.is_complete = True
        self.updated_at = datetime.now()
        return self

    def can_continue(self) -> bool:
        """判断是否可以继续执行"""
        return not self.is_complete and self.current_step < self.max_steps
