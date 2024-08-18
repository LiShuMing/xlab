"""Statistics and Cost model schemas (DESIGN.md Section 6.4)."""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class StatsGranularity(str, Enum):
    """Statistics granularity levels."""
    TABLE = "table"
    COLUMN = "column"
    PARTITION = "partition"
    HISTOGRAM = "histogram"


class StatisticsInfo(BaseModel):
    """Statistics schema (DESIGN.md Section 6.4)."""
    stats_source: str = Field(..., description="Statistics collection source")
    stats_objects: List[str] = Field(
        default_factory=list, description="Statistics objects collected"
    )
    stats_granularity: StatsGranularity = Field(
        StatsGranularity.COLUMN, description="Granularity of statistics"
    )
    storage_location: Optional[str] = Field(
        None, description="Where statistics are stored"
    )
    collection_trigger: Optional[str] = Field(
        None, description="What triggers statistics collection"
    )
    collection_scheduler: Optional[str] = Field(
        None, description="How collection is scheduled"
    )
    operator_estimation_logic: Optional[str] = Field(
        None, description="How stats are used for cardinality estimation"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )


class CostModel(BaseModel):
    """Cost schema (DESIGN.md Section 6.4)."""
    cost_formula_location: Optional[str] = Field(
        None, description="Where cost formulas are defined"
    )
    cost_dimensions: List[str] = Field(
        default_factory=list, description="Cost dimensions considered"
    )
    operator_costs: Dict[str, str] = Field(
        default_factory=dict, description="Cost formula per operator"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )