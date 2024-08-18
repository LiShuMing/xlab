"""Lifecycle Analyzer Agent for optimizer lifecycle analysis."""

from os import makedirs
from os.path import exists, join
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import AgentResult, BaseAgent
from optimizer_analysis.agents.repo_mapper import RepoMap


class PhaseInfo(BaseModel):
    """Information about a single phase in the optimizer lifecycle.

    This model captures the essential attributes of an optimization phase,
    including its name, entry point, description, and transition targets.
    """

    phase: str = Field(..., description="Name of the optimization phase")
    entry: Optional[str] = Field(
        None,
        description="Entry point file/function for this phase"
    )
    description: Optional[str] = Field(
        None,
        description="Brief description of what this phase does"
    )
    transitions_to: List[str] = Field(
        default_factory=list,
        description="List of phases this phase can transition to"
    )


class LifecycleInfo(BaseModel):
    """Complete lifecycle information for an optimizer engine.

    This model captures the full lifecycle of an optimizer, including
    all phases, their sequence, and key boundary points.
    """

    engine: str = Field(..., description="Name of the optimizer engine")
    phases: List[PhaseInfo] = Field(
        default_factory=list,
        description="List of all phases in the optimizer lifecycle"
    )
    phase_sequence: List[str] = Field(
        default_factory=list,
        description="Ordered sequence of phase names"
    )
    logical_physical_boundary: Optional[str] = Field(
        None,
        description="Point where logical to physical transformation occurs"
    )
    best_plan_selection: Optional[str] = Field(
        None,
        description="Point/mechanism for selecting the best plan"
    )
    post_optimizer: Optional[str] = Field(
        None,
        description="Post-optimizer stage description"
    )
    fallback_behavior: Optional[str] = Field(
        None,
        description="Fallback behavior when optimizer fails or times out"
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level of the lifecycle analysis: high, medium, low"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Additional notes about the lifecycle analysis"
    )


class LifecycleAgent(BaseAgent):
    """Agent for analyzing optimizer lifecycle phases.

    This agent identifies and documents the lifecycle phases of an
    optimizer engine, including phase transitions, logical to physical
    boundaries, and post-optimizer stages.
    """

    name = "LifecycleAnalyzer"

    def __init__(self, engine: str, work_dir: str, repo_map: Optional[RepoMap] = None):
        """Initialize the lifecycle analyzer agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            repo_map: Optional RepoMap providing repository structure context.
        """
        super().__init__(engine, work_dir)
        self.repo_map = repo_map

    def execute(self) -> AgentResult:
        """Execute the lifecycle analysis task.

        Returns:
            AgentResult containing the LifecycleInfo and execution status.
            The status is 'partial' with needs_manual_review=True since
            lifecycle analysis requires domain expertise.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create framework subdirectory
            framework_dir = join(self.work_dir, "framework")
            if not exists(framework_dir):
                makedirs(framework_dir, exist_ok=True)

            # Create initial lifecycle info with placeholder values
            # This indicates the analysis needs manual review and completion
            lifecycle_info = LifecycleInfo(
                engine=self.engine,
                phases=[
                    PhaseInfo(
                        phase="Parsing",
                        entry=None,
                        description="SQL parsing and AST generation",
                        transitions_to=["Analysis"]
                    ),
                    PhaseInfo(
                        phase="Analysis",
                        entry=None,
                        description="Semantic analysis and query rewriting",
                        transitions_to=["LogicalPlanning"]
                    ),
                    PhaseInfo(
                        phase="LogicalPlanning",
                        entry=None,
                        description="Logical plan generation",
                        transitions_to=["PhysicalPlanning"]
                    ),
                    PhaseInfo(
                        phase="PhysicalPlanning",
                        entry=None,
                        description="Physical plan generation and cost estimation",
                        transitions_to=["Execution"]
                    ),
                    PhaseInfo(
                        phase="Execution",
                        entry=None,
                        description="Plan execution",
                        transitions_to=[]
                    ),
                ],
                phase_sequence=["Parsing", "Analysis", "LogicalPlanning", "PhysicalPlanning", "Execution"],
                logical_physical_boundary="LogicalPlanning -> PhysicalPlanning",
                best_plan_selection=None,
                post_optimizer=None,
                fallback_behavior=None,
                confidence="low",
                notes=[
                    "Initial lifecycle structure created.",
                    "This analysis requires manual review and completion.",
                    "Use engine-specific knowledge to identify actual phase boundaries.",
                    "Identify entry points for each phase from repo_map if available.",
                    "Document best plan selection mechanism.",
                    "Document post-optimizer stages if applicable.",
                    "Document fallback behavior if applicable.",
                    "Mark confidence as 'high' after verification."
                ]
            )

            # If repo_map is provided, add context-specific notes
            if self.repo_map:
                lifecycle_info.notes.append(
                    f"Repo map available with {len(self.repo_map.main_entries)} main entries."
                )
                if self.repo_map.optimizer_dirs:
                    lifecycle_info.notes.append(
                        f"Optimizer directories identified: {', '.join(self.repo_map.optimizer_dirs)}"
                    )

            # Save the lifecycle info as JSON artifact
            lifecycle_json_path = join(framework_dir, "lifecycle.json")
            with open(lifecycle_json_path, "w") as f:
                f.write(lifecycle_info.model_dump_json(indent=2))
            artifacts.append(lifecycle_json_path)

            return AgentResult(
                agent_name=self.name,
                status="partial",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Created initial lifecycle analysis for {self.engine}. "
                    f"Requires manual review to identify actual phase details. "
                    f"Lifecycle info saved to {lifecycle_json_path}"
                ),
                metadata={
                    "needs_manual_review": True,
                    "confidence": "low",
                    "phases_count": len(lifecycle_info.phases),
                    "has_repo_map": self.repo_map is not None
                }
            )

        except Exception as e:
            errors.append(f"Failed to create lifecycle analysis: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Lifecycle analysis failed for {self.engine}",
                metadata={
                    "error": str(e)
                }
            )