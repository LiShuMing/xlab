"""Run directory path management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """Manages all paths within a single run directory.

    This immutable dataclass provides a centralized way to manage
    all file paths for a paper analysis run.
    """

    root: Path

    def __post_init__(self) -> None:
        """Ensure root is a Path object."""
        object.__setattr__(self, "root", Path(self.root))

    # Top-level files
    @property
    def metadata(self) -> Path:
        """Path to metadata.json."""
        return self.root / "metadata.json"

    @property
    def config(self) -> Path:
        """Path to config.json."""
        return self.root / "config.json"

    # raw_text/
    @property
    def raw_text_dir(self) -> Path:
        """Directory for raw text extraction."""
        return self.root / "raw_text"

    @property
    def pages(self) -> Path:
        """Path to pages.json."""
        return self.raw_text_dir / "pages.json"

    @property
    def sections(self) -> Path:
        """Path to sections.json."""
        return self.raw_text_dir / "sections.json"

    # parsed/
    @property
    def parsed_dir(self) -> Path:
        """Directory for parsed content."""
        return self.root / "parsed"

    @property
    def chunks(self) -> Path:
        """Path to chunks.jsonl."""
        return self.parsed_dir / "chunks.jsonl"

    @property
    def figures(self) -> Path:
        """Path to figures.json."""
        return self.parsed_dir / "figures.json"

    @property
    def tables(self) -> Path:
        """Path to tables.json."""
        return self.parsed_dir / "tables.json"

    # index/
    @property
    def index_dir(self) -> Path:
        """Directory for search indices."""
        return self.root / "index"

    @property
    def faiss_index(self) -> Path:
        """Path to FAISS index file."""
        return self.index_dir / "faiss.index"

    @property
    def bm25_index(self) -> Path:
        """Path to BM25 pickle file."""
        return self.index_dir / "bm25.pkl"

    @property
    def chunk_metadata(self) -> Path:
        """Path to chunk metadata JSON."""
        return self.index_dir / "chunk_metadata.json"

    # extracted/
    @property
    def extracted_dir(self) -> Path:
        """Directory for extracted information."""
        return self.root / "extracted"

    @property
    def paper_schema(self) -> Path:
        """Path to paper_schema.json."""
        return self.extracted_dir / "paper_schema.json"

    @property
    def evidence(self) -> Path:
        """Path to evidence.json."""
        return self.extracted_dir / "evidence.json"

    @property
    def related(self) -> Path:
        """Path to related.json."""
        return self.extracted_dir / "related.json"

    # reports/
    @property
    def reports_dir(self) -> Path:
        """Directory for generated reports."""
        return self.root / "reports"

    def report(self, template: str) -> Path:
        """Get path for a specific report template.

        Args:
            template: Report template name

        Returns:
            Path to the report markdown file
        """
        return self.reports_dir / f"{template}.md"

    # traces/
    @property
    def traces_dir(self) -> Path:
        """Directory for execution traces."""
        return self.root / "traces"

    def trace(self, stage: str) -> Path:
        """Get path for a specific stage trace.

        Args:
            stage: Pipeline stage name

        Returns:
            Path to the trace JSON file
        """
        return self.traces_dir / f"stage_{stage}.json"

    # prompts/
    @property
    def prompts_dir(self) -> Path:
        """Directory for saved prompts."""
        return self.root / "prompts"

    def prompt(self, name: str) -> Path:
        """Get path for a saved prompt.

        Args:
            name: Prompt name

        Returns:
            Path to the prompt text file
        """
        return self.prompts_dir / f"{name}.txt"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        for d in [
            self.raw_text_dir,
            self.parsed_dir,
            self.index_dir,
            self.extracted_dir,
            self.reports_dir,
            self.traces_dir,
            self.prompts_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
