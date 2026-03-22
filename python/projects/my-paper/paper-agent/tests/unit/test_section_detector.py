"""Unit tests for section_detector module."""

import pytest

from paper_agent.parser.section_detector import (
    _is_section_heading,
    _normalize_title,
    assign_section_to_blocks,
    detect_sections,
)


class TestIsectionHeading:
    def test_known_section_abstract(self):
        assert _is_section_heading("Abstract") is True

    def test_known_section_introduction(self):
        assert _is_section_heading("Introduction") is True

    def test_known_section_conclusion(self):
        assert _is_section_heading("Conclusion") is True

    def test_numbered_section(self):
        assert _is_section_heading("1. Introduction") is True
        assert _is_section_heading("2.1 Related Work") is True

    def test_allcaps_section(self):
        assert _is_section_heading("ABSTRACT") is True
        assert _is_section_heading("INTRODUCTION") is True

    def test_prose_sentence_not_heading(self):
        assert _is_section_heading("This paper presents a novel approach.") is False

    def test_long_text_not_heading(self):
        long = "A" * 90
        assert _is_section_heading(long) is False

    def test_ends_with_period_not_heading(self):
        assert _is_section_heading("Introduction.") is False

    def test_multiline_not_heading(self):
        assert _is_section_heading("Line one\nLine two\nLine three") is False

    def test_limitations_section(self):
        assert _is_section_heading("Limitations") is True


class TestNormalizeTitle:
    def test_removes_numbering(self):
        assert _normalize_title("1. Introduction") == "introduction"
        assert _normalize_title("2.1 Related Work") == "related work"

    def test_lowercase(self):
        assert _normalize_title("ABSTRACT") == "abstract"

    def test_strips_whitespace(self):
        assert _normalize_title("  Conclusion  ") == "conclusion"


class TestDetectSections:
    def _make_pages_data(self, pages: list) -> dict:
        return {"total_pages": len(pages), "pages": pages}

    def _make_page(self, page_num: int, blocks: list[str]) -> dict:
        return {
            "page_num": page_num,
            "text": "\n".join(blocks),
            "text_blocks": [
                {"text": t, "bbox": [0, i * 50, 500, (i + 1) * 50], "block_num": i}
                for i, t in enumerate(blocks)
            ],
            "width": 595.0,
            "height": 842.0,
        }

    def test_detects_abstract_and_introduction(self):
        pages_data = self._make_pages_data([
            self._make_page(1, ["Abstract", "This paper presents...", "Introduction", "We study..."]),
        ])
        sections = detect_sections(pages_data)
        titles_norm = [s["normalized_title"] for s in sections]
        assert "abstract" in titles_norm
        assert "introduction" in titles_norm

    def test_section_start_page(self):
        pages_data = self._make_pages_data([
            self._make_page(1, ["Abstract", "Text of abstract."]),
            self._make_page(2, ["Introduction", "Intro text here."]),
        ])
        sections = detect_sections(pages_data)
        intro = next((s for s in sections if s["normalized_title"] == "introduction"), None)
        assert intro is not None
        assert intro["start_page"] == 2

    def test_end_page_filled(self):
        pages_data = self._make_pages_data([
            self._make_page(1, ["Abstract", "Text."]),
            self._make_page(2, ["Introduction", "Intro."]),
            self._make_page(3, ["Conclusion", "Done."]),
        ])
        sections = detect_sections(pages_data)
        assert all(s["end_page"] is not None for s in sections)

    def test_empty_document(self):
        pages_data = self._make_pages_data([
            self._make_page(1, ["No headings here, just normal text about experiments."]),
        ])
        sections = detect_sections(pages_data)
        assert sections == []


class TestAssignSectionToBlocks:
    def _make_data(self, blocks_per_page: list[list[str]]) -> tuple[dict, list]:
        pages = []
        for i, blocks in enumerate(blocks_per_page):
            pages.append({
                "page_num": i + 1,
                "text": "\n".join(blocks),
                "text_blocks": [
                    {"text": t, "bbox": [0, j * 50, 500, (j + 1) * 50], "block_num": j}
                    for j, t in enumerate(blocks)
                ],
                "width": 595.0,
                "height": 842.0,
            })
        pages_data = {"total_pages": len(pages), "pages": pages}
        return pages_data, pages

    def test_blocks_assigned_to_sections(self):
        pages_data, _ = self._make_data([
            ["Abstract", "Abstract text.", "Introduction", "Intro text."],
        ])
        from paper_agent.parser.section_detector import detect_sections
        sections = detect_sections(pages_data)
        annotated = assign_section_to_blocks(pages_data, sections)

        # Find a block with "Abstract text."
        abs_block = next((b for b in annotated if b["text"] == "Abstract text."), None)
        assert abs_block is not None
        assert abs_block["section_normalized"] == "abstract"

        intro_block = next((b for b in annotated if b["text"] == "Intro text."), None)
        assert intro_block is not None
        assert intro_block["section_normalized"] == "introduction"
