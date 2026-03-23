"""Generate Markdown reports from extracted paper schema and evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger, set_agent_step

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"

_TEMPLATE_PROMPTS: dict[str, Path] = {
    "deep-dive": _PROMPT_DIR / "report_deep_dive.txt",
    "summary": _PROMPT_DIR / "report_summary.txt",
}


def generate_report(
    schema: PaperSchema,
    evidence: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    llm: LLMClient,
    template: str = "deep-dive",
) -> str:
    """Generate a Markdown report for the given template.

    Args:
        schema: Extracted paper schema
        evidence: Evidence bindings
        chunks: Text chunks for context
        llm: LLM client instance
        template: Report template name

    Returns:
        Generated Markdown report
    """
    set_agent_step(f"generate_report_{template}")
    prompt_file = _TEMPLATE_PROMPTS.get(template, _TEMPLATE_PROMPTS["deep-dive"])
    system_prompt = prompt_file.read_text(encoding="utf-8")

    schema_text = _format_schema(schema)
    evidence_text = _format_evidence(evidence)

    prompt = f"""Write a paper reading report for the following paper.

<paper_schema>
{schema_text}
</paper_schema>

<evidence>
{evidence_text}
</evidence>

Template: {template}
Generate the complete Markdown report now."""

    logger.info("generating_report", template=template, schema_title=schema.title[:50])
    report = llm.complete(prompt, system=system_prompt, max_tokens=3000)
    logger.info("report_generated", template=template, length=len(report))
    return report


def _format_schema(schema: PaperSchema) -> str:
    """Format schema for report generation.

    Args:
        schema: Paper schema

    Returns:
        Formatted schema string
    """
    lines: list[str] = [
        f"Title: {schema.title}",
        f"Authors: {', '.join(schema.authors)}" if schema.authors else "Authors: Unknown",
        f"Venue: {schema.venue or 'N/A'} ({schema.year or 'N/A'})",
        f"\nProblem Statement:\n{schema.problem_statement}",
        "\nMain Contributions:",
    ]
    for i, c in enumerate(schema.main_contributions, 1):
        lines.append(f"  {i}. {c.text}")
    lines.append(f"\nMethod Summary:\n{schema.method_summary}")
    lines.append(f"\nExperiment Setup:\n{schema.experiment_setup}")
    lines.append("\nKey Results:")
    for r in schema.key_results:
        result_line = f"  - {r.claim}"
        if r.metric:
            result_line += f" ({r.metric})"
        if r.comparison_target:
            result_line += f" vs {r.comparison_target}"
        lines.append(result_line)
    if schema.limitations:
        lines.append("\nLimitations:")
        for lim in schema.limitations:
            lines.append(f"  - {lim}")
    return "\n".join(lines)


def _format_evidence(evidence: list[dict[str, Any]]) -> str:
    """Format evidence for report generation.

    Args:
        evidence: Evidence bindings

    Returns:
        Formatted evidence string
    """
    if not evidence:
        return "No evidence bound."
    parts: list[str] = []
    for e in evidence[:15]:  # limit to avoid context overflow
        pages = ", ".join(f"p{p}" for p in e.get("page_numbers", []))
        quote = e.get("quote", "")
        support = e.get("support_type", "inferred")
        part = (
            f"Claim: {e['claim']}\n"
            f"Support: {support} | Pages: {pages or 'N/A'}"
        )
        if quote:
            part += f' | Quote: "{quote}"'
        parts.append(part)
    return "\n\n".join(parts)
