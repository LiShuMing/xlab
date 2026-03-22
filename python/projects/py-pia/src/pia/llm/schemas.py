"""Pydantic schemas for structured LLM output."""

from pydantic import BaseModel


class ReleaseExtraction(BaseModel):
    """Structured extraction of key facts from a release note.

    This is the output of Stage A (structured extraction) before the full
    analysis report is generated.
    """

    version: str
    core_features: list[str]
    breaking_changes: list[str]
    categories: dict[str, list[str]]  # e.g. performance: [...], storage: [...]
    target_audience: list[str]
    release_type: str  # major | minor | patch
    inferred_direction: list[str]


class AnalysisReport(BaseModel):
    """Structured analysis report sections.

    Represents the expected output of Stage B (expert analysis).
    The actual report is generated as markdown; this schema is used
    for validation when structured output is required.
    """

    tldr: str
    what_changed: str
    why_it_matters: str
    product_direction: str
    impact_on_users: dict[str, str]  # role -> impact description
    competitive_view: str
    caveats: str
    evidence_links: list[str]
