"""Run directory path management."""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class RunPaths:
    """Manages all paths within a single run directory."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    # Top-level files
    @property
    def metadata(self) -> Path:
        return self.root / "metadata.json"

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    # raw_text/
    @property
    def raw_text_dir(self) -> Path:
        return self.root / "raw_text"

    @property
    def pages(self) -> Path:
        return self.raw_text_dir / "pages.json"

    @property
    def sections(self) -> Path:
        return self.raw_text_dir / "sections.json"

    # parsed/
    @property
    def parsed_dir(self) -> Path:
        return self.root / "parsed"

    @property
    def chunks(self) -> Path:
        return self.parsed_dir / "chunks.jsonl"

    @property
    def figures(self) -> Path:
        return self.parsed_dir / "figures.json"

    @property
    def tables(self) -> Path:
        return self.parsed_dir / "tables.json"

    # index/
    @property
    def index_dir(self) -> Path:
        return self.root / "index"

    @property
    def faiss_index(self) -> Path:
        return self.index_dir / "faiss.index"

    @property
    def bm25_index(self) -> Path:
        return self.index_dir / "bm25.pkl"

    @property
    def chunk_metadata(self) -> Path:
        return self.index_dir / "chunk_metadata.json"

    # extracted/
    @property
    def extracted_dir(self) -> Path:
        return self.root / "extracted"

    @property
    def paper_schema(self) -> Path:
        return self.extracted_dir / "paper_schema.json"

    @property
    def evidence(self) -> Path:
        return self.extracted_dir / "evidence.json"

    @property
    def related(self) -> Path:
        return self.extracted_dir / "related.json"

    # reports/
    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    def report(self, template: str) -> Path:
        return self.reports_dir / f"{template}.md"

    # traces/
    @property
    def traces_dir(self) -> Path:
        return self.root / "traces"

    def trace(self, stage: str) -> Path:
        return self.traces_dir / f"stage_{stage}.json"

    # prompts/
    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    def prompt(self, name: str) -> Path:
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
