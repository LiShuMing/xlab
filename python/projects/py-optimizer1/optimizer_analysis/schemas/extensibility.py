"""Extensibility schema (DESIGN.md Section 6.6)."""
from typing import List, Optional

from pydantic import BaseModel, Field

from optimizer_analysis.schemas.base import Evidence


class Extensibility(BaseModel):
    """Extensibility schema (DESIGN.md Section 6.6).

    Captures how an optimizer supports extensions for rules, properties,
    cost models, and statistics through plugins and custom implementations.
    """

    rule_extension_path: Optional[str] = Field(
        default=None,
        description="Path or API for custom rule extensions"
    )
    property_extension_path: Optional[str] = Field(
        default=None,
        description="Path or API for custom property extensions"
    )
    cost_extension_path: Optional[str] = Field(
        default=None,
        description="Path or API for custom cost model extensions"
    )
    stats_extension_path: Optional[str] = Field(
        default=None,
        description="Path or API for custom statistics extensions"
    )
    plugin_registration: Optional[str] = Field(
        default=None,
        description="How plugins are registered with the optimizer"
    )
    testing_support: Optional[str] = Field(
        default=None,
        description="Testing support for extensions (e.g., test harnesses)"
    )
    uncertain_points: List[str] = Field(
        default_factory=list,
        description="Points where extensibility is uncertain or unclear"
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="Evidence supporting this analysis"
    )