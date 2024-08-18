"""Prompts module for optimizer analysis."""

from optimizer_analysis.prompts.rule_prompts import (
    RULE_EXTRACTION_SYSTEM_PROMPT,
    RULE_EXTRACTION_USER_PROMPT,
    RBO_RULE_PROMPT,
    CBO_RULE_PROMPT,
)
from optimizer_analysis.prompts.stats_prompts import (
    STATS_EXTRACTION_PROMPT,
    COST_EXTRACTION_PROMPT,
)
from optimizer_analysis.prompts.property_prompts import (
    PROPERTY_EXTRACTION_PROMPT,
    PROPERTY_SYSTEM_PROMPT,
    PROPERTY_ANALYSIS_PROMPT,
)

__all__ = [
    "RULE_EXTRACTION_SYSTEM_PROMPT",
    "RULE_EXTRACTION_USER_PROMPT",
    "CBO_RULE_PROMPT",
    "RBO_RULE_PROMPT",
    "STATS_EXTRACTION_PROMPT",
    "COST_EXTRACTION_PROMPT",
    "PROPERTY_EXTRACTION_PROMPT",
    "PROPERTY_SYSTEM_PROMPT",
    "PROPERTY_ANALYSIS_PROMPT",
]