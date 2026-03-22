"""Integration tests for the parse command."""

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_agent.cli.main import app

runner = CliRunner()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def sample_pdf() -> Path:
    """Return path to sample PDF fixture (any PDF in fixtures/)."""
    pdfs = list(FIXTURES_DIR.glob("*.pdf"))
    if not pdfs:
        pytest.skip("No PDF fixture found. Add a PDF to tests/fixtures/ to run integration tests.")
    return pdfs[0]


@pytest.fixture()
def temp_output():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestParseCommand:
    def test_parse_help(self):
        result = runner.invoke(app, ["parse", "--help"])
        assert result.exit_code == 0
        assert "Parse a PDF" in result.output

    def test_parse_nonexistent_file(self, temp_output):
        result = runner.invoke(app, ["parse", "nonexistent.pdf", "-o", str(temp_output)])
        assert result.exit_code != 0

    def test_parse_produces_output_files(self, sample_pdf, temp_output):
        result = runner.invoke(app, [
            "parse",
            str(sample_pdf),
            "-o", str(temp_output),
            "--force",
        ])
        assert result.exit_code == 0, result.output

        run_dir = temp_output / sample_pdf.stem
        assert (run_dir / "metadata.json").exists()
        assert (run_dir / "config.json").exists()
        assert (run_dir / "raw_text" / "pages.json").exists()
        assert (run_dir / "raw_text" / "sections.json").exists()
        assert (run_dir / "parsed" / "chunks.jsonl").exists()
        assert (run_dir / "parsed" / "figures.json").exists()
        assert (run_dir / "parsed" / "tables.json").exists()

    def test_parse_pages_json_structure(self, sample_pdf, temp_output):
        runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--force"])
        pages_file = temp_output / sample_pdf.stem / "raw_text" / "pages.json"
        data = json.loads(pages_file.read_text())
        assert "total_pages" in data
        assert "pages" in data
        assert data["total_pages"] > 0
        page = data["pages"][0]
        assert "page_num" in page
        assert "text_blocks" in page

    def test_parse_chunks_jsonl_structure(self, sample_pdf, temp_output):
        runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--force"])
        chunks_file = temp_output / sample_pdf.stem / "parsed" / "chunks.jsonl"
        lines = chunks_file.read_text().strip().splitlines()
        assert len(lines) > 0
        chunk = json.loads(lines[0])
        required_fields = ["chunk_id", "document_id", "section", "page_start", "page_end", "text"]
        for field in required_fields:
            assert field in chunk, f"Missing field: {field}"

    def test_parse_metadata_json_structure(self, sample_pdf, temp_output):
        runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--force"])
        meta_file = temp_output / sample_pdf.stem / "metadata.json"
        data = json.loads(meta_file.read_text())
        assert "document_id" in data
        assert "filename" in data
        assert "sha256" in data
        assert "stages" in data
        assert data["stages"]["parse"] == "completed"
        assert data["stages"]["chunk"] == "completed"

    def test_parse_resume_skips_completed_stages(self, sample_pdf, temp_output):
        # First run
        runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--force"])
        # Second run with --resume should succeed and skip
        result = runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--resume"])
        assert result.exit_code == 0
        assert "Skipping" in result.output

    def test_parse_fails_without_force_on_existing_dir(self, sample_pdf, temp_output):
        runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output), "--force"])
        result = runner.invoke(app, ["parse", str(sample_pdf), "-o", str(temp_output)])
        assert result.exit_code != 0
