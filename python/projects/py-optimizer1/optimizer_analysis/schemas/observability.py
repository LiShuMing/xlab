"""Observability schema (DESIGN.md Section 6.5)."""
from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class RuleFireVisibility(str, Enum):
    """Visibility level for rule firing information."""
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class Observability(BaseModel):
    """Observability/Explainability schema (DESIGN.md Section 6.5).

    Captures how an optimizer exposes its internal state and decision-making
    process through EXPLAIN commands, trace interfaces, and debug hooks.
    """
    explain_interfaces: List[str] = Field(
        default_factory=list,
        description="EXPLAIN command variants supported by the engine"
    )
    trace_interfaces: List[str] = Field(
        default_factory=list,
        description="Trace/debug interfaces for optimizer inspection"
    )
    rule_fire_visibility: Literal["full", "partial", "none"] = Field(
        default="none",
        description="Visibility level for rule firing information"
    )
    memo_dump_support: bool = Field(
        default=False,
        description="Whether memo/search space dump is supported"
    )
    session_controls: List[str] = Field(
        default_factory=list,
        description="Session-level optimizer control variables"
    )
    debug_hooks: List[str] = Field(
        default_factory=list,
        description="Debug hooks or flags for optimizer inspection"
    )
    uncertain_points: List[str] = Field(
        default_factory=list,
        description="Points where observability is uncertain or unclear"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="Evidence supporting this analysis"
    )