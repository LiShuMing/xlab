"""
Base class for custom tools in the AI Lab Platform.
Tools can be used by agents for various tasks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ToolInputSchema(BaseModel):
    """Base input schema for tools."""
    pass


class BaseTool(ABC):
    """
    Abstract base class for all tools.
    
    Attributes:
        name: Tool name for identification.
        description: Tool description for agent to understand usage.
        input_schema: Pydantic model for input validation.
    """
    
    name: str = "base_tool"
    description: str = "Base tool description"
    input_schema: type[BaseModel] = ToolInputSchema
    
    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters.
        
        Returns:
            Tool execution result as string.
        """
        pass
    
    def get_description_with_schema(self) -> str:
        """
        Get tool description including input schema info.
        
        Returns:
            Enhanced description for LLM.
        """
        schema_desc = []
        for field_name, field_info in self.input_schema.model_fields.items():
            desc = field_info.description or "No description"
            schema_desc.append(f"  - {field_name}: {desc}")
        
        return f"{self.description}\nParameters:\n" + "\n".join(schema_desc)
    
    def to_langchain_tool(self) -> Any:
        """
        Convert to LangChain tool format.
        
        Returns:
            LangChain StructuredTool instance.
        """
        from langchain_core.tools import StructuredTool
        
        return StructuredTool.from_function(
            func=self.run,
            name=self.name,
            description=self.get_description_with_schema(),
            args_schema=self.input_schema
        )
