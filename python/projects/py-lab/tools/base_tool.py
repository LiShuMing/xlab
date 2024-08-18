"""
Base class for custom tools in the AI Lab Platform.

Tools can be used by agents for various tasks. Each tool must define
its input schema and execution logic.
"""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class ToolInputSchema(BaseModel):
    """Base input schema for tools."""
    pass


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Tools are functions that agents can call to perform actions or
    retrieve information. Each tool must define:
    - name: Unique identifier
    - description: What the tool does (used by LLM to select tools)
    - input_schema: Pydantic model for parameter validation
    - run(): The actual execution logic
    
    Attributes:
        name: Tool name for identification
        description: Tool description for agent to understand usage
        input_schema: Pydantic model for input validation
    """
    
    name: str = "base_tool"
    description: str = "Base tool description"
    input_schema: type[BaseModel] = ToolInputSchema
    
    def __init__(self) -> None:
        """Initialize tool with logger."""
        self.logger = get_logger(f"tool.{self.name}")
    
    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters validated by input_schema
        
        Returns:
            Tool execution result as string
        
        Raises:
            ToolExecutionError: If tool execution fails
        
        Example:
            >>> tool = MyTool()
            >>> result = tool.run(query="search term")
            >>> print(result)
        """
        pass
    
    def get_description_with_schema(self) -> str:
        """
        Get tool description including input schema info.
        
        Returns:
            Enhanced description for LLM with parameter details
        """
        schema_desc: list[str] = []
        for field_name, field_info in self.input_schema.model_fields.items():
            desc = field_info.description or "No description"
            field_type = field_info.annotation.__name__ if hasattr(field_info.annotation, "__name__") else str(field_info.annotation)
            schema_desc.append(f"  - {field_name} ({field_type}): {desc}")
        
        if schema_desc:
            return f"{self.description}\nParameters:\n" + "\n".join(schema_desc)
        return self.description
    
    def to_langchain_tool(self) -> StructuredTool:
        """
        Convert to LangChain tool format.
        
        Returns:
            LangChain StructuredTool instance ready for agent use
        """
        return StructuredTool.from_function(
            func=self.run,
            name=self.name,
            description=self.get_description_with_schema(),
            args_schema=self.input_schema
        )
    
    def _log_execution_start(self, **kwargs: Any) -> None:
        """Log tool execution start."""
        self.logger.info(
            "tool_execution_started",
            tool_name=self.name,
            parameters=list(kwargs.keys())
        )
    
    def _log_execution_complete(self, result: str, duration_ms: float | None = None) -> None:
        """Log tool execution completion."""
        log_data: dict[str, Any] = {
            "tool_name": self.name,
            "result_length": len(result),
        }
        if duration_ms:
            log_data["duration_ms"] = round(duration_ms, 2)
        self.logger.info("tool_execution_completed", **log_data)
    
    def _log_execution_error(self, error: Exception) -> None:
        """Log tool execution error."""
        self.logger.error(
            "tool_execution_failed",
            tool_name=self.name,
            error_type=type(error).__name__,
            error=str(error)
        )


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""
    
    def __init__(self, tool_name: str, message: str, cause: Exception | None = None):
        """
        Initialize tool execution error.
        
        Args:
            tool_name: Name of the tool that failed
            message: Error message
            cause: Original exception that caused the failure
        """
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")


class ToolRegistry:
    """Registry for managing available tools."""
    
    _tools: dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool_class: type[BaseTool]) -> type[BaseTool]:
        """
        Register a tool class.
        
        Args:
            tool_class: Class inheriting from BaseTool
            
        Returns:
            The same class (for decorator chaining)
        """
        instance = tool_class()
        cls._tools[instance.name] = instance
        logger.info("tool_registered", name=instance.name)
        return tool_class
    
    @classmethod
    def get_tool(cls, name: str) -> BaseTool | None:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return cls._tools.get(name)
    
    @classmethod
    def get_all_tools(cls) -> dict[str, BaseTool]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary of tool names to instances
        """
        return cls._tools.copy()
    
    @classmethod
    def get_langchain_tools(cls) -> list[StructuredTool]:
        """
        Get all tools as LangChain StructuredTools.
        
        Returns:
            List of LangChain tool instances
        """
        return [tool.to_langchain_tool() for tool in cls._tools.values()]
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools."""
        cls._tools.clear()
        logger.info("tool_registry_cleared")


def register_tool(tool_class: type[BaseTool]) -> type[BaseTool]:
    """
    Convenience decorator for tool registration.
    
    Args:
        tool_class: Class inheriting from BaseTool
    
    Returns:
        The same class (for decorator chaining)
    
    Example:
        >>> @register_tool
        ... class WebSearchTool(BaseTool):
        ...     name = "web_search"
        ...     description = "Search the web for information"
        ...     input_schema = WebSearchInput
        ...     
        ...     def run(self, query: str) -> str:
        ...         # Implementation
        ...         pass
    """
    return ToolRegistry.register(tool_class)
