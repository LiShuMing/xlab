"""Bind claims from PaperSchema to source chunks as evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_agent.extraction.paper_schema import PaperSchema
from paper_agent.llm.client import LLMClient
from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)

_PROMPT_FILE = Path(__file__).parent.parent / "llm" / "prompts" / "bind_evidence.txt"


def bind_evidence(
    schema: PaperSchema,
    chunks: list[dict[str, Any]],
    llm: LLMClient,
    top_k_chunks: int = 12,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """
    For each claim in the schema, find supporting chunks.

    Processes claims in small batches to avoid context overflow.
    Returns a list of evidence records.
    """
    system_prompt = _PROMPT_FILE.read_text()

    # Collect all claims to bind (limit total)
    claims = []
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
        batch = claims[i:i + batch_size]
        claims_text = "\n".join(f"{j+1}. {c}" for j, c in enumerate(batch))

        prompt = f"""Here are the claims to bind to evidence:

<claims>
{claims_text}
</claims>

Here are the available paper chunks:

<chunks>
{chunk_context}
</chunks>

For each claim, identify the best supporting chunk(s)."""

        logger.info("binding_evidence_batch", batch=i // batch_size + 1, claims=len(batch))

        try:
            raw = llm.complete_json(prompt, system=system_prompt, max_tokens=1500)
        except Exception as e:
            logger.error("evidence_binding_batch_failed", error=str(e))
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

        # Pad missing
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

    logger.info("evidence_bound", total=len(all_evidence))
    return all_evidence


def _select_relevant_chunks(
    chunks: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Select chunks for evidence pool, skipping references."""
    filtered = [c for c in chunks if "reference" not in c.get("section_normalized", "")]
    return filtered[:top_k]


def _format_chunk_pool(chunks: list[dict[str, Any]]) -> str:
    parts = []
    for c in chunks:
        sec = c.get("section", c.get("section_normalized", ""))
        pages = f"p{c['page_start']}-{c['page_end']}"
        parts.append(
            f"[id:{c['chunk_id'][:8]} | {sec} | {pages}]\n{c['text'][:400]}"
        )
    return "\n\n".join(parts)


def _fallback_evidence(claims: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "claim": c,
            "support_type": "inferred",
            "source_chunk_ids": [],
            "page_numbers": [],
            "quote": "",
            "figure_refs": [],
            "table_refs": [],
        }
        for c in claims
    ]
