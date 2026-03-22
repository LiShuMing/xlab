"""Section detection from parsed PDF pages."""

from __future__ import annotations

import re
from typing import Any

from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Common academic paper section titles
_KNOWN_SECTIONS = [
    "abstract",
    "introduction",
    "related work",
    "background",
    "preliminaries",
    "method",
    "methods",
    "methodology",
    "approach",
    "model",
    "framework",
    "architecture",
    "experiment",
    "experiments",
    "experimental setup",
    "experimental results",
    "evaluation",
    "results",
    "discussion",
    "analysis",
    "ablation",
    "conclusion",
    "conclusions",
    "future work",
    "acknowledgment",
    "acknowledgments",
    "acknowledgements",
    "references",
    "appendix",
    "limitations",
]

_SECTION_RE = re.compile(
    r"^(\d+\.?\d*\.?\s+)?([A-Z][A-Za-z\s\-:]+)$"
)


def detect_sections(pages_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Detect sections from parsed pages.

    Handles two PDF layouts:
    1. Section title is its own block (standalone heading)
    2. Section title is the first line(s) of a block (ACM/IEEE two-column style)

    Returns:
        [
            {
                "title": str,
                "normalized_title": str,
                "start_page": int,
                "start_block": int,
                "end_page": int | None,
            }
        ]
    """
    sections = []
    pages = pages_data["pages"]

    for page in pages:
        page_num = page["page_num"]
        for i, block in enumerate(page["text_blocks"]):
            text = block["text"].strip()
            heading = _extract_heading_from_block(text)
            if heading:
                normalized = _normalize_title(heading)
                sections.append({
                    "title": heading,
                    "normalized_title": normalized,
                    "start_page": page_num,
                    "start_block": i,
                    "end_page": None,
                })

    # Fill end_page
    for i in range(len(sections) - 1):
        sections[i]["end_page"] = sections[i + 1]["start_page"]
    if sections:
        sections[-1]["end_page"] = pages[-1]["page_num"]

    logger.info("sections_detected", count=len(sections))
    return sections


def _is_section_heading(text: str) -> bool:
    """Heuristic to identify section headings."""
    lines = text.strip().splitlines()
    if len(lines) > 2:
        return False
    first_line = lines[0].strip()

    # Too long to be a heading
    if len(first_line) > 80:
        return False

    # Must not end with period (prose sentence)
    if first_line.endswith("."):
        return False

    # Reject if contains math/unicode symbols (Korean/CJK-compat chars used in math PDFs)
    # PyMuPDF renders math chars in private-use / hangul-compat range
    if re.search(r"[\uac00-\ud7ff\u3130-\u318f\uf900-\ufaff\u2200-\u22ff\u0300-\u036f]", first_line):
        return False

    normalized = _normalize_title(first_line)
    if normalized in _KNOWN_SECTIONS:
        return True

    # Numbered section: "1. Introduction", "2.1 Related Work"
    if re.match(r"^\d+\.?\d*\.?\s+[A-Z]", first_line):
        return True

    # All-caps short title: "ABSTRACT", "INTRODUCTION"
    if first_line.isupper() and 3 < len(first_line) < 50:
        return True

    return False


def _extract_heading_from_block(text: str) -> str | None:
    """
    Extract a section heading from a block, even if the block contains body text.

    Handles two patterns:
    - Standalone heading: the entire block is a heading
    - Embedded heading: first 1-2 lines of block match a heading pattern (ACM style)
      e.g. "1\nINTRODUCTION\nWith the rapid evolution..."
           "4.2\nIncremental Maintenance Part\nThis part..."
    """
    lines = text.splitlines()
    if not lines:
        return None

    # Pattern 1: standalone heading (1-2 lines, whole block)
    if len(lines) <= 2 and _is_section_heading(text):
        return lines[0].strip()

    # Pattern 2: numbered section embedded at start of block
    # "1\nINTRODUCTION\n..." or "4.2\nIncremental Maintenance Part\n..."
    if len(lines) >= 2:
        first = lines[0].strip()
        second = lines[1].strip()
        # First line is just a section number like "1", "4.2", "A"
        if re.match(r"^\d+\.?\d*\.?$", first) or re.match(r"^[A-Z]\.$", first):
            candidate = f"{first} {second}"
            if _is_section_heading(candidate):
                return candidate

    # Pattern 3: "4.2\nIncremental Maintenance Part\nThis part..." where number+title are merged
    # Handle "4.2\nTitle Here\nbody text" — check second line as heading
    if len(lines) >= 3:
        # Check if line[1] looks like a title
        second = lines[1].strip()
        if _is_section_heading(second):
            return second

    # Pattern 4: ABSTRACT/REFERENCES embedded as first word before newline
    if len(lines) >= 2:
        first = lines[0].strip()
        normalized = _normalize_title(first)
        if normalized in _KNOWN_SECTIONS and not first.endswith("."):
            return first

    return None


def _normalize_title(text: str) -> str:
    """Normalize a section title for comparison."""
    # Remove leading numbers like "1.", "2.1", "A."
    text = re.sub(r"^\d+\.?\d*\.?\s*", "", text)
    text = re.sub(r"^[A-Z]\.\s*", "", text)
    return text.strip().lower()


def assign_section_to_blocks(
    pages_data: dict[str, Any],
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return all text blocks with their assigned section.

    Returns:
        [
            {
                "page_num": int,
                "block_num": int,
                "text": str,
                "bbox": list,
                "section": str,
                "section_normalized": str,
            }
        ]
    """
    # Build a lookup: (page_num, block_idx) -> section
    block_section: dict[tuple[int, int], tuple[str, str]] = {}

    pages = pages_data["pages"]
    page_map = {p["page_num"]: p for p in pages}

    for sec_idx, section in enumerate(sections):
        start_page = section["start_page"]
        end_page = section["end_page"] or pages[-1]["page_num"]
        start_block = section["start_block"]

        # Determine exclusive end block on the end_page (where the next section starts)
        next_section = sections[sec_idx + 1] if sec_idx + 1 < len(sections) else None
        next_start_page = next_section["start_page"] if next_section else None
        next_start_block = next_section["start_block"] if next_section else None

        for pn in range(start_page, end_page + 1):
            page = page_map.get(pn)
            if not page:
                continue
            for bi, block in enumerate(page["text_blocks"]):
                # Skip blocks before the section heading on the start page
                if pn == start_page and bi < start_block:
                    continue
                # Stop before the next section's heading block on its start page
                if next_section and pn == next_start_page and bi >= next_start_block:
                    continue
                key = (pn, bi)
                block_section[key] = (
                    section["title"],
                    section["normalized_title"],
                )

    result = []
    for page in pages:
        pn = page["page_num"]
        for bi, block in enumerate(page["text_blocks"]):
            sec_title, sec_norm = block_section.get((pn, bi), ("", ""))
            result.append({
                "page_num": pn,
                "block_num": bi,
                "text": block["text"],
                "bbox": block["bbox"],
                "section": sec_title,
                "section_normalized": sec_norm,
            })

    return result
