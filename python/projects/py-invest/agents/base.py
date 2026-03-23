"""Agent system base classes and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from modules.report_generator.types import Report


@dataclass
class ToolParameter:
    """Tool parameter definition.

    Attributes:
        name: Parameter name.
        type: Parameter type (string, number, integer, boolean, array, object).
        description: Parameter description.
        required: Whether parameter is required.
        enum: Allowed values (if applicable).
        default: Default value (if applicable).
    """

    name: str
    type: str
    description: str
    required: bool = False
    enum: Optional[list] = None
    default: Optional[Any] = None


@dataclass
class ToolInfo:
    """Tool metadata for LLM discovery.

    Attributes:
        name: Tool name.
        description: Tool description.
        parameters: Parameter definitions.
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)


class BaseAgentTool(ABC):
    """Abstract base class for agent tools.

    Subclasses must implement get_info() and execute() methods.

    Example:
        class QueryPriceTool(BaseAgentTool):
            name = "query_price"
            description = "Query stock price"

            def get_info(self) -> ToolInfo:
                return ToolInfo(...)

            async def execute(self, args: dict) -> str:
                return "Price data..."
    """

    name: str = "base_tool"
    description: str = "Base tool"

    @abstractmethod
    def get_info(self) -> ToolInfo:
        """Get tool information for LLM discovery.

        Returns:
            ToolInfo instance.
        """
        pass

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute tool logic.

        Args:
            arguments: Tool arguments.

        Returns:
            Result string.
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> bool:
        """Validate parameters.

        Args:
            params: Parameters to validate.

        Returns:
            True if valid.
        """
        info = self.get_info()
        for param in info.parameters:
            if param.required and param.name not in params:
                return False
        return True

    def get_schema(self) -> dict:
        """Get JSON Schema representation.

        Returns:
            JSON Schema dictionary.
        """
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
    """Tool execution result.

    Attributes:
        success: Whether execution succeeded.
        result: Result string.
        error: Error message (if failed).
        tool_name: Tool name.
        execution_time: Execution duration in seconds.
        metadata: Additional metadata.
    """

    success: bool
    result: str = ""
    error: Optional[str] = None
    tool_name: str = ""
    execution_time: float = 0.0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, result: str, tool_name: str = "", metadata: dict = None) -> "ToolResult":
        """Create successful result.

        Args:
            result: Result string.
            tool_name: Tool name.
            metadata: Additional metadata.

        Returns:
            ToolResult instance.
        """
        return cls(
            success=True,
            result=result,
            tool_name=tool_name,
            metadata=metadata or {},
        )

    @classmethod
    def fail(cls, error: str, tool_name: str = "") -> "ToolResult":
        """Create failed result.

        Args:
            error: Error message.
            tool_name: Tool name.

        Returns:
            ToolResult instance.
        """
        return cls(
            success=False,
            error=error,
            tool_name=tool_name,
        )


@dataclass
class AgentState:
    """Agent execution state.

    Attributes:
        messages: Conversation messages.
        tool_calls: Tool call history.
        tool_results: Tool execution results.
        current_step: Current step number.
        max_steps: Maximum steps allowed.
        is_complete: Whether execution is complete.
        final_response: Final response string.
        report: Structured Report object (for multi-agent pipeline).
        error: Error message (if failed).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 10
    is_complete: bool = False
    final_response: Optional[str] = None
    report: Optional["Report"] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str) -> "AgentState":
        """Add message to state.

        Args:
            role: Message role (user/assistant/system).
            content: Message content.

        Returns:
            Self for method chaining.
        """
        self.messages.append({"role": role, "content": content, "timestamp": datetime.now()})
        self.updated_at = datetime.now()
        return self

    def add_tool_call(self, tool_name: str, args: dict) -> "AgentState":
        """Add tool call to state.

        Args:
            tool_name: Tool name.
            args: Tool arguments.

        Returns:
            Self for method chaining.
        """
        self.tool_calls.append(
            {"tool_name": tool_name, "args": args, "timestamp": datetime.now()}
        )
        self.updated_at = datetime.now()
        return self

    def add_tool_result(self, result: ToolResult) -> "AgentState":
        """Add tool result to state.

        Args:
            result: Tool result.

        Returns:
            Self for method chaining.
        """
        self.tool_results.append(result)
        self.updated_at = datetime.now()
        return self

    def next_step(self) -> int:
        """Advance to next step.

        Returns:
            New step number.
        """
        self.current_step += 1
        self.updated_at = datetime.now()
        return self.current_step

    def complete(self, response: str) -> "AgentState":
        """Mark execution as complete.

        Args:
            response: Final response.

        Returns:
            Self for method chaining.
        """
        self.is_complete = True
        self.final_response = response
        self.updated_at = datetime.now()
        return self

    def fail(self, error: str) -> "AgentState":
        """Mark execution as failed.

        Args:
            error: Error message.

        Returns:
            Self for method chaining.
        """
        self.error = error
        self.is_complete = True
        self.updated_at = datetime.now()
        return self

    def can_continue(self) -> bool:
        """Check if execution can continue.

        Returns:
            True if not complete and under max steps.
        """
        return not self.is_complete and self.current_step < self.max_steps
