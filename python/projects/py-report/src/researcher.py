"""Researcher: calls API using Anthropic SDK to generate deep research reports.

This module now delegates to the agent-based pipeline while maintaining
backward compatibility with the existing API.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from dotenv import load_dotenv

from .agent import ResearchAgent, ResearchMode, ResearchOptions
from .exceptions import ResearcherError
from .report_manager import save_report

# Load ~/.env first for LLM config, then local .env for project overrides
load_dotenv(Path.home() / ".env")
load_dotenv(override=True)
log = structlog.get_logger()


def _map_depth_to_mode(depth: str) -> ResearchMode:
    """Map legacy depth parameter to ResearchMode."""
    mapping = {
        "standard": ResearchMode.STANDARD,
        "deep": ResearchMode.DEEP,
        "executive": ResearchMode.EXECUTIVE,
    }
    return mapping.get(depth.lower(), ResearchMode.DEEP)


async def generate_report_async(
    product_name: str,
    report_language: str = "English",
    research_depth: str = "deep",
    prompts_path: Path | None = None,
    timeout: float = 120.0,
    mode: str | None = None,
    competitors: list[str] | None = None,
) -> str:
    """Generate a research report using the agent-based pipeline.

    Args:
        product_name: Name of the LLM API product to research.
        report_language: Language for the report (default: English).
        research_depth: Research depth - standard, deep, or executive.
        prompts_path: Path to prompts manifest (unused in agent mode).
        timeout: Timeout for LLM API calls.
        mode: Research mode (overrides depth if provided).
        competitors: List of competitors for comparison analysis.

    Returns:
        Generated report as markdown string.

    Raises:
        ResearcherError: If the research fails.
    """
    # Use mode if provided, otherwise map from depth
    research_mode = (
        ResearchMode(mode) if mode else _map_depth_to_mode(research_depth)
    )

    options = ResearchOptions(
        mode=research_mode,
        language=report_language,
        depth=research_depth,
        competitors=competitors or [],
    )

    agent = ResearchAgent.create_default(timeout=timeout)

    try:
        report = await agent.research(product_name, options)
    except Exception as exc:
        raise ResearcherError(f"Research failed: {exc}") from exc

    # Check if the report is empty (indicates failure)
    if not report.raw_markdown and not report.executive_summary:
        raise ResearcherError("Research failed: No content generated")

    return report.to_markdown()


def generate_and_save(
    product_name: str,
    report_language: str = "English",
    research_depth: str = "deep",
    prompts_path: Path | None = None,
    mode: str | None = None,
    competitors: list[str] | None = None,
) -> Path:
    """Synchronous wrapper: generate and persist a report.

    Args:
        product_name: Name of the LLM API product to research.
        report_language: Language for the report (default: English).
        research_depth: Research depth - standard, deep, or executive.
        prompts_path: Path to prompts manifest (unused in agent mode).
        mode: Research mode (overrides depth if provided).
        competitors: List of competitors for comparison analysis.

    Returns:
        Path to the saved report file.
    """
    content = asyncio.run(
        generate_report_async(
            product_name,
            report_language,
            research_depth,
            prompts_path,
            mode=mode,
            competitors=competitors,
        )
    )
    return save_report(product_name, content)


if __name__ == "__main__":
    import sys

    product = sys.argv[1] if len(sys.argv) > 1 else "OpenAI GPT-4o"
    depth = sys.argv[2] if len(sys.argv) > 2 else "deep"
    path = generate_and_save(product, research_depth=depth)
    print(f"Report saved to {path}")