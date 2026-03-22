"""Generate Markdown reports from extracted paper schema and evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"

_TEMPLATE_PROMPTS = {
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
    """Generate a Markdown report for the given template."""
    prompt_file = _TEMPLATE_PROMPTS.get(template, _TEMPLATE_PROMPTS["deep-dive"])
    system_prompt = prompt_file.read_text()

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

    logger.info("generating_report", template=template)
    report = llm.complete(prompt, system=system_prompt, max_tokens=3000)
    return report


def _format_schema(schema: PaperSchema) -> str:
    lines = [
        f"Title: {schema.title}",
        f"Authors: {', '.join(schema.authors)}",
        f"Venue: {schema.venue or 'N/A'} ({schema.year or 'N/A'})",
        f"\nProblem Statement:\n{schema.problem_statement}",
        f"\nMain Contributions:",
    ]
    for i, c in enumerate(schema.main_contributions, 1):
        lines.append(f"  {i}. {c.text}")
    lines.append(f"\nMethod Summary:\n{schema.method_summary}")
    lines.append(f"\nExperiment Setup:\n{schema.experiment_setup}")
    lines.append(f"\nKey Results:")
    for r in schema.key_results:
        result_line = f"  - {r.claim}"
        if r.metric:
            result_line += f" ({r.metric})"
        if r.comparison_target:
            result_line += f" vs {r.comparison_target}"
        lines.append(result_line)
    if schema.limitations:
        lines.append(f"\nLimitations:")
        for lim in schema.limitations:
            lines.append(f"  - {lim}")
    return "\n".join(lines)


def _format_evidence(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "No evidence bound."
    parts = []
    for e in evidence[:15]:  # limit to avoid context overflow
        pages = ", ".join(f"p{p}" for p in e.get("page_numbers", []))
        quote = e.get("quote", "")
        support = e.get("support_type", "inferred")
        parts.append(
            f"Claim: {e['claim']}\n"
            f"Support: {support} | Pages: {pages or 'N/A'}"
            + (f" | Quote: \"{quote}\"" if quote else "")
        )
    return "\n\n".join(parts)
