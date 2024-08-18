from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class PropertyType(str, Enum):
    """Property classification type (DESIGN.md Section 6.3)."""
    LOGICAL = "logical"
    PHYSICAL = "physical"


class TraitProperty(BaseModel):
    """Trait/Property schema (DESIGN.md Section 6.3)."""
    property_name: str = Field(..., description="Property name")
    property_type: PropertyType = Field(..., description="Logical or physical property")
    representation: Optional[str] = Field(
        None, description="How property is represented in code"
    )
    propagation_logic: Optional[str] = Field(
        None, description="How property propagates through operators"
    )
    enforcer: Optional[str] = Field(
        None, description="Enforcer operator for this property"
    )
    where_used: List[str] = Field(
        default_factory=list, description="Operators using this property"
    )
    impact_on_search: Optional[str] = Field(
        None, description="How property affects search space"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )
    confidence: str = Field(
        "medium",
        description="Confidence level of the analysis: high, medium, low, unknown"
    )
    uncertain_points: List[str] = Field(
        default_factory=list,
        description="Points needing manual review"
    )