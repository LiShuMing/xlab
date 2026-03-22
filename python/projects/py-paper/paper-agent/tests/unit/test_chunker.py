"""Unit tests for chunker module."""

import pytest

from paper_agent.parser.chunker import chunk_blocks, _group_by_section


def _make_blocks(entries: list[tuple[str, str, int]]) -> list[dict]:
    """Make annotated blocks from (text, section_normalized, page_num) tuples."""
    blocks = []
    for i, (text, section_norm, page_num) in enumerate(entries):
        blocks.append({
            "text": text,
            "section": section_norm.title(),
            "section_normalized": section_norm,
            "page_num": page_num,
            "block_num": i,
            "bbox": [0, 0, 500, 50],
        })
    return blocks


class TestGroupBySection:
    def test_groups_consecutive_same_section(self):
        blocks = _make_blocks([
            ("text1", "abstract", 1),
            ("text2", "abstract", 1),
            ("text3", "introduction", 2),
        ])
        groups = _group_by_section(blocks)
        assert len(groups) == 2
        assert groups[0][0] == "abstract"
        assert len(groups[0][1]) == 2
        assert groups[1][0] == "introduction"

    def test_empty_blocks(self):
        assert _group_by_section([]) == []

    def test_single_block(self):
        blocks = _make_blocks([("only text", "abstract", 1)])
        groups = _group_by_section(blocks)
        assert len(groups) == 1


class TestChunkBlocks:
    DOC_ID = "test-doc-123"

    def test_basic_chunking_produces_chunks(self):
        blocks = _make_blocks([
            ("A" * 100, "introduction", 1),
            ("B" * 100, "introduction", 1),
            ("C" * 100, "methods", 2),
        ])
        chunks = chunk_blocks(blocks, self.DOC_ID, chunk_size=150, chunk_overlap=20)
        assert len(chunks) > 0

    def test_chunk_has_required_fields(self):
        blocks = _make_blocks([("Some text here.", "abstract", 1)])
        chunks = chunk_blocks(blocks, self.DOC_ID)
        assert len(chunks) > 0
        chunk = chunks[0]
        assert "chunk_id" in chunk
        assert "document_id" in chunk
        assert chunk["document_id"] == self.DOC_ID
        assert "section" in chunk
        assert "section_normalized" in chunk
        assert "page_start" in chunk
        assert "page_end" in chunk
        assert "text" in chunk
        assert "figure_refs" in chunk
        assert "table_refs" in chunk
        assert chunk["figure_refs"] == []
        assert chunk["table_refs"] == []

    def test_skip_references(self):
        blocks = _make_blocks([
            ("Main content.", "introduction", 1),
            ("Ref 1. Ref 2.", "references", 5),
        ])
        chunks = chunk_blocks(blocks, self.DOC_ID, skip_references=True)
        sections = {c["section_normalized"] for c in chunks}
        assert "references" not in sections
        assert "introduction" in sections

    def test_large_text_split_into_multiple_chunks(self):
        # A single section with text much larger than chunk_size
        long_text = " ".join(["word"] * 500)  # ~2500 chars
        blocks = _make_blocks([(long_text, "methods", 3)])
        chunks = chunk_blocks(blocks, self.DOC_ID, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 2

    def test_chunk_ids_are_unique(self):
        blocks = _make_blocks([
            ("A" * 200, "introduction", 1),
            ("B" * 200, "methods", 2),
            ("C" * 200, "results", 3),
        ])
        chunks = chunk_blocks(blocks, self.DOC_ID, chunk_size=150, chunk_overlap=20)
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_page_range_preserved(self):
        blocks = _make_blocks([
            ("Text on page 1.", "introduction", 1),
            ("Text on page 2.", "introduction", 2),
        ])
        chunks = chunk_blocks(blocks, self.DOC_ID, chunk_size=2000)
        # Should be one chunk covering pages 1-2
        assert chunks[0]["page_start"] == 1
        assert chunks[0]["page_end"] == 2

    def test_empty_blocks(self):
        chunks = chunk_blocks([], self.DOC_ID)
        assert chunks == []
