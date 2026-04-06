"""Engine configuration models for optimizer analysis."""

from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas import EngineType, OptimizerStyle


class EngineConfig(BaseModel):
    """Configuration for an optimizer engine.

    Contains metadata about the engine's repository, optimizer style,
    and key paths for analysis.
    """

    name: str = Field(..., description="Engine name identifier")
    repo_url: Optional[str] = Field(None, description="Repository URL")
    default_branch: str = Field("main", description="Default git branch")
    engine_type: EngineType = Field(..., description="Engine classification type")
    optimizer_style: OptimizerStyle = Field(..., description="Optimizer architectural style")
    optimizer_dirs: List[str] = Field(
        default_factory=list, description="Directories containing optimizer code"
    )
    main_entry: Optional[str] = Field(None, description="Primary optimizer entry point")
    fallback_paths: List[str] = Field(
        default_factory=list, description="Fallback optimizer paths if primary fails"
    )
    docs_url: Optional[str] = Field(None, description="Documentation URL")
    notes: List[str] = Field(
        default_factory=list, description="Additional notes about the engine"
    )