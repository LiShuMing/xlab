"""Paper structure schema (Pydantic models)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Contribution(BaseModel):
    text: str
    confidence: float = 1.0


class KeyResult(BaseModel):
    claim: str
    metric: Optional[str] = None
    comparison_target: Optional[str] = None


class PaperSchema(BaseModel):
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    venue: Optional[str] = None
    year: Optional[str] = None
    problem_statement: str = ""
    main_contributions: list[Contribution] = Field(default_factory=list)
    method_summary: str = ""
    experiment_setup: str = ""
    key_results: list[KeyResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "PaperSchema":
        # Coerce year to string
        if data.get("year") is not None:
            data["year"] = str(data["year"])

        # Normalize contributions
        contribs = []
        for c in data.get("main_contributions", []):
            if isinstance(c, str):
                contribs.append(Contribution(text=c))
            elif isinstance(c, dict):
                contribs.append(Contribution(**c))
        data["main_contributions"] = contribs

        # Normalize key_results
        results = []
        for r in data.get("key_results", []):
            if isinstance(r, str):
                results.append(KeyResult(claim=r))
            elif isinstance(r, dict):
                results.append(KeyResult(**r))
        data["key_results"] = results

        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})
