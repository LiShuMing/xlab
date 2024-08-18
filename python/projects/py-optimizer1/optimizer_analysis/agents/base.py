"""Base agent class and AgentResult model."""

from abc import ABC, abstractmethod
from os.path import join
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Result of an agent execution."""

    agent_name: str = Field(..., description="Name of the agent that produced this result")
    status: str = Field(
        ...,
        description="Execution status: 'success', 'failed', or 'partial'"
    )
    artifacts: List[str] = Field(
        default_factory=list,
        description="List of generated artifact file paths"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages"
    )
    summary: str = Field(
        ...,
        description="Brief summary of the execution result"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution"
    )


class BaseAgent(ABC):
    """Abstract base class for all analysis agents."""

    name: str = "base_agent"

    def __init__(self, engine: str, work_dir: str):
        """Initialize the agent.

        Args:
            engine: The optimizer engine name this agent works with.
            work_dir: Working directory for storing artifacts.
        """
        self.engine = engine
        self.work_dir = work_dir

    @abstractmethod
    def execute(self) -> AgentResult:
        """Execute the agent's main task.

        Returns:
            AgentResult containing the execution outcome.
        """
        pass

    def _artifact_path(self, filename: str) -> str:
        """Get full path for an artifact file.

        Args:
            filename: Name of the artifact file.

        Returns:
            Full path to the artifact file in the work directory.
        """
        return join(self.work_dir, filename)