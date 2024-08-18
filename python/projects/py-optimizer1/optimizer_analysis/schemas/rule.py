from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class RuleCategory(str, Enum):
    """Rule classification category (DESIGN.md Section 6.2)."""
    RBO = "rbo"
    CBO = "cbo"
    SCALAR = "scalar"
    POST_OPT = "post_opt"
    IMPLICIT = "implicit"


class ImplementationType(str, Enum):
    """How explicitly a rule is implemented (DESIGN.md Section 9)."""
    EXPLICIT = "explicitly_implemented"
    IMPLICIT = "implicitly_implemented"
    FRAMEWORK_PROVIDED = "framework_provided"
    NOT_APPLICABLE = "not_applicable"


class Rule(BaseModel):
    """Rule schema (DESIGN.md Section 6.2)."""
    rule_id: str = Field(..., description="Unique rule identifier")
    rule_name: str = Field(..., description="Human-readable rule name")
    engine: str = Field(..., description="Engine this rule belongs to")
    rule_category: RuleCategory = Field(..., description="Rule type classification")
    implementation_type: ImplementationType = Field(
        ImplementationType.EXPLICIT, description="Implementation explicitness"
    )
    lifecycle_stage: Optional[str] = Field(
        None, description="When this rule fires in optimizer lifecycle"
    )
    source_files: List[str] = Field(
        default_factory=list, description="Source files implementing this rule"
    )
    registration_points: List[str] = Field(
        default_factory=list, description="Where rule is registered"
    )
    trigger_pattern: Optional[str] = Field(
        None, description="Pattern that triggers this rule"
    )
    preconditions: List[str] = Field(
        default_factory=list, description="Preconditions for rule application"
    )
    transformation_logic: Optional[str] = Field(
        None, description="What the rule transforms"
    )
    input_operators: List[str] = Field(
        default_factory=list, description="Input operator types"
    )
    output_operators: List[str] = Field(
        default_factory=list, description="Output operator types"
    )
    relational_algebra_form: Optional[str] = Field(
        None, description="Relation algebra expression"
    )
    depends_on_stats: bool = Field(
        False, description="Whether rule uses statistics"
    )
    depends_on_cost: bool = Field(
        False, description="Whether rule uses cost model"
    )
    depends_on_property: bool = Field(
        False, description="Whether rule uses physical properties"
    )
    examples: List[str] = Field(
        default_factory=list, description="Example transformations"
    )
    confidence: str = Field(
        "medium", description="Confidence level: high, medium, low, unknown"
    )
    uncertain_points: List[str] = Field(
        default_factory=list, description="Points needing manual review"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this analysis"
    )