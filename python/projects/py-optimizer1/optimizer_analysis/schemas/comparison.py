"""Comparison schemas for engine analysis comparison (DESIGN.md Section 6.2)."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class ComparisonDimension(str, Enum):
    """Dimensions for comparing optimizer engines."""
    LIFECYCLE = "lifecycle"
    RULE_COVERAGE = "rule_coverage"
    PROPERTY_SYSTEM = "property_system"
    STATS_COST = "stats_cost"
    OBSERVABILITY = "observability"
    EXTENSIBILITY = "extensibility"


class ComparisonCell(BaseModel):
    """A single cell in the comparison matrix."""
    engine: str = Field(..., description="Engine being compared")
    dimension: ComparisonDimension = Field(..., description="Dimension being evaluated")
    value: str = Field(..., description="Cell value (e.g., 'yes', 'no', 'partial', 'explicit', 'implicit', 'n/a')")
    details: Optional[str] = Field(None, description="Additional details about the value")
    evidence: List[Evidence] = Field(
        default_factory=list, description="Evidence supporting this cell"
    )


class ComparisonMatrix(BaseModel):
    """Matrix comparing engines across dimensions."""
    engines: List[str] = Field(..., description="List of engines being compared")
    dimensions: List[ComparisonDimension] = Field(..., description="Dimensions evaluated")
    cells: List[ComparisonCell] = Field(default_factory=list, description="Matrix cells")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="When the matrix was generated"
    )


class ComparisonReport(BaseModel):
    """Complete comparison report for multiple engines."""
    title: str = Field(..., description="Report title")
    engines_compared: List[str] = Field(..., description="Engines included in comparison")
    matrices: List[ComparisonMatrix] = Field(default_factory=list, description="Comparison matrices")
    findings: List[str] = Field(default_factory=list, description="Key findings from comparison")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations based on comparison")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="When the report was generated"
    )