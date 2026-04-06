from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class EngineType(str, Enum):
    """Engine classification type (DESIGN.md Section 4.1)."""
    COLUMNAR_OLAP = "columnar_olap"
    ROW_STORE = "row_store"
    FRAMEWORK = "framework"
    RESEARCH_PROTO = "research_proto"
    HYBRID = "hybrid"


class OptimizerStyle(str, Enum):
    """Optimizer architectural style (DESIGN.md Section 4.1)."""
    CASCADES = "cascades"
    VOLCANO = "volcano"
    PLANNER_PATH_ENUM = "planner_path_enum"
    HEURISTIC_MIXED = "heuristic_mixed"
    ANALYZER_PLANNER = "analyzer_planner"


class OptimizerPhase(str, Enum):
    """Standard optimizer lifecycle phases."""
    PARSING = "parsing"
    LOGICAL_OPT = "logical_opt"
    PHYSICAL_OPT = "physical_opt"
    COST_ESTIMATION = "cost_estimation"
    BEST_PLAN_SELECTION = "best_plan_selection"
    POST_OPTIMIZER = "post_optimizer"


class Framework(BaseModel):
    """Framework schema (DESIGN.md Section 6.1)."""
    engine_name: str = Field(..., description="Engine name")
    engine_type: EngineType = Field(..., description="Engine classification")
    optimizer_style: OptimizerStyle = Field(..., description="Optimizer architectural style")
    main_entry: str = Field(..., description="Primary optimizer entry point")
    optimizer_phases: Optional[List[OptimizerPhase]] = Field(
        None, description="Lifecycle phases in order"
    )
    logical_physical_split: bool = Field(
        False, description="Whether logical and physical optimization are separate"
    )
    memo_or_equivalent: Optional[str] = Field(
        None, description="Memo structure or equivalent search space"
    )
    search_strategy: Optional[str] = Field(
        None, description="Plan search strategy description"
    )
    best_plan_selection: Optional[str] = Field(
        None, description="How best plan is selected"
    )
    post_optimizer_stage: Optional[str] = Field(
        None, description="Post-optimizer stage description"
    )
    fallback_paths: Optional[List[str]] = Field(
        None, description="Fallback optimizer paths if primary fails"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )