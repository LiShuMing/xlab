"""Repository Mapper Agent for mapping optimizer repository structure."""

from os import makedirs
from os.path import exists, join
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.agents.base import AgentResult, BaseAgent


class RepoMap(BaseModel):
    """Repository structure map for an optimizer engine.

    This model captures the essential directory and file locations
    relevant to optimizer analysis within a repository.
    """

    engine: str = Field(..., description="Name of the optimizer engine")
    repo_root: str = Field(..., description="Root path of the repository")
    optimizer_dirs: List[str] = Field(
        default_factory=list,
        description="Optimizer-related directories"
    )
    main_entries: List[str] = Field(
        default_factory=list,
        description="Main optimizer entry files"
    )
    rule_registry: List[str] = Field(
        default_factory=list,
        description="Rule registration files"
    )
    stats_dir: Optional[str] = Field(
        None,
        description="Statistics-related directory"
    )
    cost_dir: Optional[str] = Field(
        None,
        description="Cost model-related directory"
    )
    explain_dir: Optional[str] = Field(
        None,
        description="Explain/trace-related directory"
    )
    call_graph_seeds: List[str] = Field(
        default_factory=list,
        description="Seed files for call graph analysis"
    )
    fallback_paths: List[str] = Field(
        default_factory=list,
        description="Fallback paths when primary paths are unavailable"
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level of the mapping: high, medium, low"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Additional notes about the repository mapping"
    )


class RepoMapperAgent(BaseAgent):
    """Agent for mapping repository structure of an optimizer engine.

    This agent identifies key directories, entry points, rule registries,
    and other relevant paths for optimizer analysis.
    """

    name = "RepoMapper"

    def __init__(self, engine: str, work_dir: str, repo_root: str):
        """Initialize the repository mapper agent.

        Args:
            engine: The optimizer engine name.
            work_dir: Working directory for storing artifacts.
            repo_root: Root path of the repository to map.
        """
        super().__init__(engine, work_dir)
        self.repo_root = repo_root

    def execute(self) -> AgentResult:
        """Execute the repository mapping task.

        Returns:
            AgentResult containing the RepoMap and execution status.
        """
        errors: List[str] = []
        artifacts: List[str] = []

        try:
            # Ensure work directory exists
            if not exists(self.work_dir):
                makedirs(self.work_dir, exist_ok=True)

            # Create the repository map with placeholder values
            # This indicates the mapping needs manual review and completion
            repo_map = RepoMap(
                engine=self.engine,
                repo_root=self.repo_root,
                optimizer_dirs=[],
                main_entries=[],
                rule_registry=[],
                stats_dir=None,
                cost_dir=None,
                explain_dir=None,
                call_graph_seeds=[],
                fallback_paths=[],
                confidence="low",
                notes=[
                    "Initial repository map created.",
                    "This mapping requires manual review and completion.",
                    "Use engine-specific knowledge to identify optimizer directories.",
                    "Mark confidence as 'high' after verification."
                ]
            )

            # Save the repository map as JSON artifact
            map_path = self._artifact_path("repo_map.json")
            with open(map_path, "w") as f:
                f.write(repo_map.model_dump_json(indent=2))
            artifacts.append(map_path)

            return AgentResult(
                agent_name=self.name,
                status="partial",
                artifacts=artifacts,
                errors=errors,
                summary=(
                    f"Created initial repository map for {self.engine}. "
                    f"Requires manual review to identify optimizer paths. "
                    f"Map saved to {map_path}"
                ),
                metadata={
                    "repo_root": self.repo_root,
                    "needs_manual_review": True,
                    "confidence": "low"
                }
            )

        except Exception as e:
            errors.append(f"Failed to create repository map: {str(e)}")
            return AgentResult(
                agent_name=self.name,
                status="failed",
                artifacts=artifacts,
                errors=errors,
                summary=f"Repository mapping failed for {self.engine}",
                metadata={
                    "repo_root": self.repo_root,
                    "error": str(e)
                }
            )