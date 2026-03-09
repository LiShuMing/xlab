"""Tests for src/prompt_learner.py."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from src.prompt_learner import (
    _extract_yaml_front_matter,
    _extract_fenced_prompt,
    _extract_blockquote,
    _extract_html_comment,
    _extract_paragraph,
    _find_first_heading_index,
    _normalize,
    _read_first_lines,
    extract_prompt,
    scan_and_learn,
    summarize_prompts,
)


def make_lines(text: str) -> list[str]:
    return text.splitlines()


class TestReadFirstLines:
    def test_reads_up_to_max_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "big.md"
        f.write_text("\n".join(str(i) for i in range(500)))
        lines = _read_first_lines(f, max_lines=300)
        assert len(lines) == 300

    def test_reads_fewer_if_file_smaller(self, tmp_path: Path) -> None:
        f = tmp_path / "small.md"
        f.write_text("a\nb\nc")
        lines = _read_first_lines(f, max_lines=300)
        assert lines == ["a", "b", "c"]

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        lines = _read_first_lines(tmp_path / "nonexistent.md")
        assert lines == []


class TestFindFirstHeadingIndex:
    def test_finds_h1(self) -> None:
        lines = ["intro", "", "# Heading"]
        assert _find_first_heading_index(lines) == 2

    def test_finds_h2(self) -> None:
        lines = ["intro", "## Section"]
        assert _find_first_heading_index(lines) == 1

    def test_no_heading(self) -> None:
        lines = ["a", "b", "c"]
        assert _find_first_heading_index(lines) == 3


class TestExtractYamlFrontMatter:
    def test_valid_yaml(self) -> None:
        lines = make_lines("---\ntitle: Test\nauthor: Me\n---\n# Heading")
        result = _extract_yaml_front_matter(lines)
        assert result is not None
        text, lr = result
        assert "title: Test" in text
        assert lr == [1, 4]

    def test_no_yaml(self) -> None:
        lines = make_lines("# Heading\nContent")
        assert _extract_yaml_front_matter(lines) is None

    def test_unclosed_yaml(self) -> None:
        lines = make_lines("---\ntitle: Test\n# Heading")
        assert _extract_yaml_front_matter(lines) is None


class TestExtractFencedPrompt:
    def test_valid_fenced(self) -> None:
        lines = make_lines("```prompt\nDo research.\n```\n# Heading")
        result = _extract_fenced_prompt(lines)
        assert result is not None
        text, lr = result
        assert "Do research." in text

    def test_no_fenced(self) -> None:
        lines = make_lines("# Heading\nContent")
        assert _extract_fenced_prompt(lines) is None


class TestExtractBlockquote:
    def test_valid_blockquote(self) -> None:
        lines = make_lines("> I am a researcher.\n> Please help.\n\n# Heading")
        result = _extract_blockquote(lines)
        assert result is not None
        text, _ = result
        assert "> I am" in text

    def test_no_blockquote(self) -> None:
        lines = make_lines("Plain text.\n\n# Heading")
        assert _extract_blockquote(lines) is None


class TestExtractHtmlComment:
    def test_valid_comment(self) -> None:
        lines = make_lines("<!-- prompt: Do this task -->\n# Heading")
        result = _extract_html_comment(lines)
        assert result is not None
        text, _ = result
        assert "Do this task" in text

    def test_no_comment(self) -> None:
        lines = make_lines("# Heading\nContent")
        assert _extract_html_comment(lines) is None


class TestExtractParagraph:
    def test_extracts_first_paragraph(self) -> None:
        lines = make_lines("First paragraph.\nContinued.\n\n# Heading")
        result = _extract_paragraph(lines)
        assert result is not None
        text, lr = result
        assert "First paragraph." in text
        assert lr[0] == 1

    def test_empty_file(self) -> None:
        assert _extract_paragraph([]) is None

    def test_only_heading(self) -> None:
        assert _extract_paragraph(make_lines("# Heading")) is None


class TestNormalize:
    def test_strips_whitespace(self) -> None:
        assert _normalize("  hello  ") == "hello"

    def test_collapses_blank_lines(self) -> None:
        text = "a\n\n\n\nb"
        result = _normalize(text)
        assert "\n\n\n" not in result


class TestExtractPrompt:
    def test_yaml_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Test\n---\n# Heading\nContent")
        result = extract_prompt(f)
        assert result is not None
        assert result["prompt_type"] == "yaml_front_matter"

    def test_paragraph_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("I am a researcher.\nHelp me.\n\n# Heading")
        result = extract_prompt(f)
        assert result is not None
        assert result["prompt_type"] == "paragraph"

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("")
        assert extract_prompt(f) is None

    def test_300_line_truncation(self, tmp_path: Path) -> None:
        # File has 400 lines, prompt paragraph is at top
        content = "Prompt paragraph.\n" + "\n".join(["line"] * 10) + "\n# Heading\n" + "\n".join(["x"] * 390)
        f = tmp_path / "big.md"
        f.write_text(content)
        result = extract_prompt(f)
        assert result is not None


class TestScanAndLearn:
    def test_scans_directory(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("Prompt text.\n\n# Heading")
        (docs / "b.md").write_text("Another prompt.\n\n## Heading")
        out = tmp_path / "prompts" / "learned.json"
        manifest = scan_and_learn(docs, out)
        assert len(manifest["prompts"]) == 2
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["schema_version"] == "1.0"

    def test_empty_directory(self, tmp_path: Path) -> None:
        docs = tmp_path / "empty_docs"
        docs.mkdir()
        out = tmp_path / "p.json"
        manifest = scan_and_learn(docs, out)
        assert manifest["prompts"] == []


class TestSummarizePrompts:
    def test_no_prompts(self) -> None:
        result = summarize_prompts({"prompts": []})
        assert "No existing" in result

    def test_with_prompts(self) -> None:
        manifest = {
            "prompts": [
                {
                    "source_file": "test.md",
                    "prompt_type": "paragraph",
                    "normalized_text": "Be a researcher.",
                }
            ]
        }
        result = summarize_prompts(manifest)
        assert "test.md" in result
