"""Paper structure schema (Pydantic models)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Contribution(BaseModel):
    """A single contribution of the paper."""

    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class KeyResult(BaseModel):
    """A key result or finding from the paper."""

    claim: str
    metric: str | None = None
    comparison_target: str | None = None


class PaperSchema(BaseModel):
    """Complete structured representation of a paper.

    This Pydantic model provides validation and serialization
    for extracted paper information.
    """

    title: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: str | None = None
    problem_statement: str = ""
    main_contributions: list[Contribution] = Field(default_factory=list)
    method_summary: str = ""
    experiment_setup: str = ""
    key_results: list[KeyResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperSchema:
        """Create a PaperSchema from a dictionary with coercion.

        Handles various input formats and normalizes data types.

        Args:
            data: Raw dictionary from LLM response or JSON

        Returns:
            Validated PaperSchema instance
        """
        # Make a copy to avoid modifying the original
        data = dict(data)

        # Coerce year to string
        if data.get("year") is not None:
            data["year"] = str(data["year"])

        # Normalize contributions (handle string or dict inputs)
        contribs: list[Contribution] = []
        for c in data.get("main_contributions", []):
            if isinstance(c, str):
                contribs.append(Contribution(text=c))
            elif isinstance(c, dict):
                contribs.append(Contribution(**c))
        data["main_contributions"] = contribs

        # Normalize key_results (handle string or dict inputs)
        results: list[KeyResult] = []
        for r in data.get("key_results", []):
            if isinstance(r, str):
                results.append(KeyResult(claim=r))
            elif isinstance(r, dict):
                results.append(KeyResult(**r))
        data["key_results"] = results

        # Filter to only valid fields
        valid_fields = set(cls.model_fields.keys())
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)

    def get_contribution_summary(self, max_items: int = 3) -> str:
        """Get a summary of main contributions.

        Args:
            max_items: Maximum number of contributions to include

        Returns:
            Formatted summary string
        """
        items = self.main_contributions[:max_items]
        return "; ".join(c.text for c in items) if items else "No contributions listed"

    def get_result_summary(self, max_items: int = 3) -> str:
        """Get a summary of key results.

        Args:
            max_items: Maximum number of results to include

        Returns:
            Formatted summary string
        """
        items = self.key_results[:max_items]
        if not items:
            return "No key results listed"
        parts = []
        for r in items:
            part = r.claim
            if r.metric:
                part += f" ({r.metric})"
            parts.append(part)
        return "; ".join(parts)
