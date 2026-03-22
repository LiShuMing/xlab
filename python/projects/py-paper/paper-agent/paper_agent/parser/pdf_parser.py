"""PDF parsing using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Parse a PDF and return structured page data.

    Returns:
        {
            "total_pages": int,
            "pages": [
                {
                    "page_num": int,  # 1-indexed
                    "text": str,
                    "text_blocks": [{"text": str, "bbox": [x0,y0,x1,y1], "block_num": int}],
                    "width": float,
                    "height": float,
                }
            ]
        }
    """
    logger.info("parsing_pdf", path=str(pdf_path))
    doc = fitz.open(str(pdf_path))

    pages = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1

        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        text_blocks = []
        full_text_parts = []

        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            if block_type != 0:  # skip image blocks
                continue
            text = text.strip()
            if not text:
                continue
            # Skip headers/footers heuristically: very short lines near page edges
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

    doc.close()
    logger.info("pdf_parsed", total_pages=len(pages))
    return {"total_pages": len(pages), "pages": pages}


def _is_header_footer(text: str, y0: float, y1: float, page_height: float) -> bool:
    """Heuristic: skip very short text blocks at top or bottom 5% of page."""
    margin = page_height * 0.05
    is_edge = y1 < margin or y0 > page_height - margin
    is_short = len(text) < 80
    is_page_num = bool(re.match(r"^\d+$", text.strip()))
    return is_edge and (is_short or is_page_num)
