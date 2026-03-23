"""Bind claims from PaperSchema to source chunks as evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger, set_agent_step

logger = get_logger(__name__)

_PROMPT_FILE = Path(__file__).parent.parent / "llm" / "prompts" / "bind_evidence.txt"


def bind_evidence(
    schema: PaperSchema,
    chunks: list[dict[str, Any]],
    llm: LLMClient,
    top_k_chunks: int = 12,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """For each claim in the schema, find supporting chunks.

    Processes claims in small batches to avoid context overflow.

    Args:
        schema: Extracted paper schema with claims
        chunks: Available text chunks
        llm: LLM client instance
        top_k_chunks: Number of chunks to include as evidence pool
        batch_size: Number of claims to process per batch

    Returns:
        List of evidence records with claim-to-chunk mappings
    """
    set_agent_step("bind_evidence")
    system_prompt = _PROMPT_FILE.read_text(encoding="utf-8")

    # Collect all claims to bind (limit total)
    claims: list[str] = []
    for c in schema.main_contributions[:4]:
        claims.append(c.text)
    for r in schema.key_results[:4]:
        claims.append(r.claim)

    if not claims:
        logger.warning("no_claims_to_bind")
        return []

    chunk_pool = _select_relevant_chunks(chunks, top_k_chunks)
    chunk_context = _format_chunk_pool(chunk_pool)

    all_evidence: list[dict[str, Any]] = []

    # Process in batches
    for i in range(0, len(claims), batch_size):
        batch = claims[i : i + batch_size]
        claims_text = "\n".join(f"{j + 1}. {c}" for j, c in enumerate(batch))

        prompt = f"""Here are the claims to bind to evidence:

<claims>
{claims_text}
</claims>

Here are the available paper chunks:

<chunks>
{chunk_context}
</chunks>

For each claim, identify the best supporting chunk(s)."""

        batch_num = i // batch_size + 1
        total_batches = (len(claims) + batch_size - 1) // batch_size
        logger.info(
            "binding_evidence_batch",
            batch=batch_num,
            total_batches=total_batches,
            claims=len(batch),
        )

        try:
            raw = llm.complete_json(prompt, system=system_prompt, max_tokens=1500)
        except Exception as e:
            logger.error("evidence_binding_batch_failed", error=str(e), batch=batch_num)
            raw = []

        if not isinstance(raw, list):
            raw = []

        for j, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            claim_text = batch[j] if j < len(batch) else item.get("claim", "")
            all_evidence.append({
                "claim": claim_text,
                "support_type": item.get("support_type", "inferred"),
                "source_chunk_ids": item.get("source_chunk_ids", []),
                "page_numbers": item.get("page_numbers", []),
                "quote": item.get("quote", ""),
                "figure_refs": item.get("figure_refs", []),
                "table_refs": item.get("table_refs", []),
            })

        # Pad missing results with fallback
        for j in range(len(raw), len(batch)):
            all_evidence.append({
                "claim": batch[j],
                "support_type": "inferred",
                "source_chunk_ids": [],
                "page_numbers": [],
                "quote": "",
                "figure_refs": [],
                "table_refs": [],
            })

    direct_count = sum(1 for e in all_evidence if e.get("support_type") == "direct")
    logger.info(
        "evidence_bound",
        total=len(all_evidence),
        direct=direct_count,
        inferred=len(all_evidence) - direct_count,
    )
    return all_evidence


def _select_relevant_chunks(
    chunks: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Select chunks for evidence pool, skipping references.

    Args:
        chunks: All available chunks
        top_k: Maximum number of chunks to select

    Returns:
        Filtered chunks
    """
    filtered = [
        c for c in chunks
        if "reference" not in c.get("section_normalized", "").lower()
    ]
    return filtered[:top_k]


def _format_chunk_pool(chunks: list[dict[str, Any]]) -> str:
    """Format chunks for evidence binding context.

    Args:
        chunks: Chunks to format

    Returns:
        Formatted context string
    """
    parts: list[str] = []
    for c in chunks:
        sec = c.get("section", c.get("section_normalized", ""))
        page_start = c.get("page_start", 0)
        page_end = c.get("page_end", 0)
        chunk_id = c.get("chunk_id", "")
        pages = f"p{page_start}-{page_end}"
        text = c.get("text", "")
        parts.append(f"[id:{chunk_id[:8]} | {sec} | {pages}]\n{text[:400]}")
    return "\n\n".join(parts)
