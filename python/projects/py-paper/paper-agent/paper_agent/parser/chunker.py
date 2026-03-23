"""Section-aware chunking of parsed PDF blocks."""

from __future__ import annotations

import uuid
from typing import Any

from paper_agent.utils.logging import get_logger, set_agent_step

logger = get_logger(__name__)

# Sections to skip when building the main retrieval index
_SKIP_SECTIONS: set[str] = {
    "references",
    "acknowledgments",
    "acknowledgements",
    "acknowledgment",
}


def chunk_blocks(
    annotated_blocks: list[dict[str, Any]],
    document_id: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
    skip_references: bool = False,
) -> list[dict[str, Any]]:
    """Convert annotated blocks into retrieval chunks.

    Strategy:
    1. Group blocks by section
    2. Within each section, split by token count with overlap
    3. Preserve section, page, and figure/table reference metadata

    Args:
        annotated_blocks: Blocks with section annotations
        document_id: Unique document identifier
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between chunks in characters
        skip_references: Whether to skip reference sections

    Returns:
        List of chunk dictionaries with metadata
    """
    set_agent_step("chunk_blocks")
    chunks: list[dict[str, Any]] = []

    # Group consecutive blocks by section
    section_groups = _group_by_section(annotated_blocks)

    for section_norm, group in section_groups:
        if skip_references and section_norm in _SKIP_SECTIONS:
            logger.debug("skipping_section", section=section_norm)
            continue

        section_title = group[0]["section"] if group else ""
        section_chunks = _split_into_chunks(
            group,
            document_id,
            section_title,
            section_norm,
            chunk_size,
            chunk_overlap,
        )
        chunks.extend(section_chunks)

    logger.info(
        "chunking_done",
        total_chunks=len(chunks),
        document_id=document_id,
        sections=len(section_groups),
    )
    return chunks


def _group_by_section(
    blocks: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group blocks into contiguous runs of the same section.

    Args:
        blocks: Annotated blocks

    Returns:
        List of (section_normalized, blocks) tuples
    """
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    current_section: str | None = None
    current_group: list[dict[str, Any]] = []

    for block in blocks:
        sec = block["section_normalized"]
        if sec != current_section:
            if current_group:
                groups.append((current_section or "", current_group))
            current_section = sec
            current_group = [block]
        else:
            current_group.append(block)

    if current_group:
        groups.append((current_section or "", current_group))

    return groups


def _split_into_chunks(
    blocks: list[dict[str, Any]],
    document_id: str,
    section_title: str,
    section_norm: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    """Split a section's blocks into overlapping chunks by character count.

    Args:
        blocks: Section blocks
        document_id: Document ID
        section_title: Human-readable section title
        section_norm: Normalized section name
        chunk_size: Target chunk size
        chunk_overlap: Overlap size

    Returns:
        List of chunk dictionaries
    """
    # Collect all text with page tracking, splitting oversized blocks
    segments: list[tuple[str, int]] = []  # (text, page_num)
    for block in blocks:
        text = block["text"].strip()
        if not text:
            continue
        if len(text) <= chunk_size:
            segments.append((text, block["page_num"]))
        else:
            # Split oversized block into sub-segments
            for sub in _split_text(text, chunk_size):
                segments.append((sub, block["page_num"]))

    if not segments:
        return []

    # Build chunks with overlap
    chunks: list[dict[str, Any]] = []
    current_texts: list[str] = []
    current_pages: list[int] = []
    current_len = 0

    def flush_chunk() -> None:
        """Write the current chunk to the list."""
        if not current_texts:
            return
        text = "\n\n".join(current_texts)
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "document_id": document_id,
            "section": section_title,
            "section_normalized": section_norm,
            "page_start": current_pages[0],
            "page_end": current_pages[-1],
            "chunk_type": "paragraph",
            "text": text,
            "figure_refs": [],
            "table_refs": [],
        })

    for text, page_num in segments:
        seg_len = len(text)

        if current_len + seg_len > chunk_size and current_texts:
            flush_chunk()
            # Keep overlap: retain last N chars worth of text
            overlap_texts: list[str] = []
            overlap_pages: list[int] = []
            overlap_len = 0
            for t, p in zip(reversed(current_texts), reversed(current_pages)):
                if overlap_len + len(t) > chunk_overlap:
                    break
                overlap_texts.insert(0, t)
                overlap_pages.insert(0, p)
                overlap_len += len(t)
            current_texts = overlap_texts
            current_pages = overlap_pages
            current_len = overlap_len

        current_texts.append(text)
        current_pages.append(page_num)
        current_len += seg_len

    flush_chunk()
    return chunks


def _split_text(text: str, max_len: int) -> list[str]:
    """Split text into parts of at most max_len characters, preferring sentence boundaries.

    Args:
        text: Text to split
        max_len: Maximum length per part

    Returns:
        List of text parts
    """
    parts: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        # Try to split at a sentence boundary
        split_at = remaining.rfind(". ", 0, max_len)
        if split_at == -1:
            split_at = max_len
        else:
            split_at += 1  # include the period
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts
