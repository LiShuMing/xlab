"""Extract structured paper schema from chunks using LLM."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_FILE = Path(__file__).parent.parent / "llm" / "prompts" / "extract_structure.txt"

# Sections to prioritize for extraction
_KEY_SECTIONS = {
    "abstract", "introduction", "conclusion", "conclusions",
    "method", "methods", "methodology", "approach",
    "contributions", "results", "evaluation", "evaluations",
    "limitations", "discussion",
}


def extract_paper_schema(
    chunks: list[dict[str, Any]],
    llm: LLMClient,
    max_context_chars: int = 12000,
) -> PaperSchema:
    """
    Extract structured paper information from chunks.

    Prioritizes abstract, intro, conclusion, and method chunks.
    """
    system_prompt = _PROMPT_FILE.read_text()

    # Select the most informative chunks
    selected = _select_chunks(chunks, max_context_chars)
    context = _format_chunks(selected)

    prompt = f"""Analyze the following academic paper chunks and extract structured information.

<paper_chunks>
{context}
</paper_chunks>

Extract the structured information as specified."""

    logger.info("extracting_schema", chunks_selected=len(selected), context_chars=len(context))

    raw = llm.complete_json(prompt, system=system_prompt, max_tokens=2048)
    schema = PaperSchema.from_dict(raw if isinstance(raw, dict) else {})

    logger.info(
        "schema_extracted",
        title=schema.title[:60],
        contributions=len(schema.main_contributions),
        results=len(schema.key_results),
    )
    return schema


def _select_chunks(
    chunks: list[dict[str, Any]],
    max_chars: int,
) -> list[dict[str, Any]]:
    """Select chunks prioritizing key sections, within character budget."""
    priority: list[dict] = []
    rest: list[dict] = []

    for chunk in chunks:
        sec = chunk.get("section_normalized", "")
        if any(k in sec for k in _KEY_SECTIONS):
            priority.append(chunk)
        else:
            rest.append(chunk)

    selected = []
    total = 0
    for chunk in priority + rest:
        text_len = len(chunk.get("text", ""))
        if total + text_len > max_chars:
            break
        selected.append(chunk)
        total += text_len

    return selected


def _format_chunks(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for c in chunks:
        sec = c.get("section", c.get("section_normalized", ""))
        pages = f"p{c['page_start']}" if c["page_start"] == c["page_end"] else f"p{c['page_start']}-{c['page_end']}"
        parts.append(f"[{sec} | {pages} | id:{c['chunk_id'][:8]}]\n{c['text']}")
    return "\n\n---\n\n".join(parts)
