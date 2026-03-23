"""PDF parsing using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from paper_agent.utils.logging import get_logger, set_agent_step

logger = get_logger(__name__)


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """Parse a PDF and return structured page data.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with:
            - total_pages: int
            - pages: list of page dictionaries with page_num, text,
                     text_blocks, width, height

    Raises:
        FileNotFoundError: If the PDF doesn't exist
        RuntimeError: If parsing fails
    """
    set_agent_step("parse_pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("parsing_pdf", path=str(pdf_path))
    doc = fitz.open(str(pdf_path))

    try:
        pages: list[dict[str, Any]] = []
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1

            blocks = page.get_text("blocks")
            text_blocks: list[dict[str, Any]] = []
            full_text_parts: list[str] = []

            for b in blocks:
                x0, y0, x1, y1, text, block_no, block_type = b
                if block_type != 0:  # skip image blocks
                    continue
                text = text.strip()
                if not text:
                    continue
                # Skip headers/footers heuristically
                if _is_header_footer(text, y0, y1, page.rect.height):
                    continue
                text_blocks.append({
                    "text": text,
                    "bbox": [x0, y0, x1, y1],
                    "block_num": block_no,
                })
                full_text_parts.append(text)

            pages.append({
                "page_num": page_num,
                "text": "\n\n".join(full_text_parts),
                "text_blocks": text_blocks,
                "width": page.rect.width,
                "height": page.rect.height,
            })

        logger.info("pdf_parsed", total_pages=len(pages), path=str(pdf_path))
        return {"total_pages": len(pages), "pages": pages}
    finally:
        doc.close()


def _is_header_footer(text: str, y0: float, y1: float, page_height: float) -> bool:
    """Heuristic: skip very short text blocks at top or bottom 5% of page.

    Args:
        text: The text content
        y0: Top Y coordinate
        y1: Bottom Y coordinate
        page_height: Total page height

    Returns:
        True if the block appears to be a header or footer
    """
    margin = page_height * 0.05
    is_edge = y1 < margin or y0 > page_height - margin
    is_short = len(text) < 80
    is_page_num = bool(re.match(r"^\d+$", text.strip()))
    return is_edge and (is_short or is_page_num)
