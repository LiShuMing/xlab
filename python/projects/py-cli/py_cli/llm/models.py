"""Pydantic models for LLM operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommitAnalysis:
    """Analysis of a single commit."""

    sha: str
    type: str  # feature, bugfix, refactor, test, docs, etc.
    summary: str
    impact: str
    modules: list[str]


@dataclass(frozen=True)
class AnalysisResult:
    """Result of repository analysis."""

    summary: str
    categories: dict[str, list[CommitAnalysis]]
    key_changes: list[str]
    architecture_direction: str
    recommendations: list[str]
    raw_response: str

    def to_markdown(self) -> str:
        """Convert analysis to markdown format."""
        lines = [
            "# Code Change Analysis Report",
            "",
            "## Executive Summary",
            "",
            self.summary,
            "",
            "## Changes by Category",
            "",
        ]

        for category, commits in self.categories.items():
            if not commits:
                continue

            lines.extend([f"### {category.title()}", ""])
            for commit in commits:
                lines.extend(
                    [
                        f"- **{commit.sha}**: {commit.summary}",
                        f"  - Impact: {commit.impact}",
                        f"  - Modules: {', '.join(commit.modules)}",
                        "",
                    ]
                )

        lines.extend(
            [
                "## Key Changes",
                "",
            ]
        )
        for change in self.key_changes:
            lines.append(f"- {change}")

        lines.extend(
            [
                "",
                "## Architecture Direction",
                "",
                self.architecture_direction,
                "",
                "## Recommendations",
                "",
            ]
        )
        for rec in self.recommendations:
            lines.append(f"- {rec}")

        return "\n".join(lines)


@dataclass(frozen=True)
class LLMResponse:
    """Raw response from LLM API."""

    content: str
    model: str
    usage: dict[str, Any]
    finish_reason: str | None
