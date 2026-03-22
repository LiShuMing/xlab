"""Pipeline runner: orchestrates all stages for a single paper."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from paper_agent.core.config import RunConfig
from paper_agent.core.paths import RunPaths
from paper_agent.core.state import RunState, Stage, STAGE_ORDER
from paper_agent.utils.io import read_json, read_jsonl, write_json
from paper_agent.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


class PipelineRunner:
    """Runs analysis pipeline stages in order, with resume/skip support."""

    def __init__(
        self,
        paths: RunPaths,
        state: RunState,
        config: RunConfig,
    ) -> None:
        self.paths = paths
        self.state = state
        self.config = config

    def run(
        self,
        from_stage: Stage | None = None,
        to_stage: Stage | None = None,
        resume: bool = False,
    ) -> None:
        """Run stages from from_stage to to_stage inclusive."""
        # Determine which stages to run
        start_idx = STAGE_ORDER.index(from_stage) if from_stage else 0
        end_idx = STAGE_ORDER.index(to_stage) + 1 if to_stage else len(STAGE_ORDER)
        stages_to_run = STAGE_ORDER[start_idx:end_idx]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for stage in stages_to_run:
                if self.state.should_skip(stage, resume):
                    console.print(f"[dim]  ↳ Skipping {stage.value} (already completed)[/dim]")
                    continue
                self._run_stage(stage, progress)

    def _run_stage(self, stage: Stage, progress: Any) -> None:
        stage_fns: dict[Stage, Callable] = {
            Stage.PARSE: self._stage_parse,
            Stage.CHUNK: self._stage_chunk,
            Stage.INDEX: self._stage_index,
            Stage.EXTRACT: self._stage_extract,
            Stage.BIND_EVIDENCE: self._stage_bind_evidence,
            Stage.RELATED: self._stage_related,
            Stage.REPORT: self._stage_report,
        }
        fn = stage_fns.get(stage)
        if not fn:
            return

        task = progress.add_task(f"[cyan]{stage.value}[/cyan]...", total=None)
        self.state.mark_in_progress(stage)
        t0 = time.time()
        try:
            msg = fn()
            self.state.mark_completed(stage)
            elapsed = time.time() - t0
            progress.update(task, description=f"[green]✓ {stage.value}[/green] {msg} ({elapsed:.1f}s)")
        except Exception as e:
            self.state.mark_failed(stage, str(e))
            progress.update(task, description=f"[red]✗ {stage.value}: {e}[/red]")
            raise

    # ── Stage implementations ──────────────────────────────────────────────

    def _stage_parse(self) -> str:
        from paper_agent.parser.pdf_parser import parse_pdf
        pdf_path = Path(self.state.filename)
        # resolve relative to original input - stored in config
        cfg_data = read_json(self.paths.config)
        # pdf path is not in config directly - stored in metadata
        meta = read_json(self.paths.metadata)
        # We need the original PDF path - store it in metadata
        pdf_str = meta.get("pdf_path", "")
        if not pdf_str:
            raise RuntimeError("pdf_path not found in metadata")
        pages_data = parse_pdf(Path(pdf_str))
        write_json(self.paths.pages, pages_data)
        return f"{pages_data['total_pages']} pages"

    def _stage_chunk(self) -> str:
        from paper_agent.parser.section_detector import detect_sections, assign_section_to_blocks
        from paper_agent.parser.chunker import chunk_blocks

        pages_data = read_json(self.paths.pages)
        meta = read_json(self.paths.metadata)
        document_id = meta["document_id"]

        sections = detect_sections(pages_data)
        write_json(self.paths.sections, sections)

        annotated = assign_section_to_blocks(pages_data, sections)
        chunks = chunk_blocks(
            annotated,
            document_id=document_id,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            skip_references=self.config.skip_references,
        )
        from paper_agent.utils.io import write_jsonl
        write_jsonl(self.paths.chunks, chunks)
        write_json(self.paths.figures, [])
        write_json(self.paths.tables, [])
        return f"{len(sections)} sections, {len(chunks)} chunks"

    def _stage_index(self) -> str:
        # Placeholder - BM25/FAISS index (Stage 2 simplified: skip for now)
        write_json(self.paths.chunk_metadata, {})
        return "index skipped (BM25/FAISS not yet implemented)"

    def _stage_extract(self) -> str:
        from paper_agent.extraction.claim_extractor import extract_paper_schema
        from paper_agent.llm.client import LLMClient

        chunks = read_jsonl(self.paths.chunks)
        llm = LLMClient(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )
        schema = extract_paper_schema(chunks, llm)
        write_json(self.paths.paper_schema, schema.model_dump())
        return f"title: {schema.title[:40]!r}"

    def _stage_bind_evidence(self) -> str:
        from paper_agent.extraction.evidence_binder import bind_evidence
        from paper_agent.extraction.paper_schema import PaperSchema
        from paper_agent.llm.client import LLMClient

        chunks = read_jsonl(self.paths.chunks)
        schema_data = read_json(self.paths.paper_schema)
        schema = PaperSchema.from_dict(schema_data)

        llm = LLMClient(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )
        evidence = bind_evidence(schema, chunks, llm)
        write_json(self.paths.evidence, evidence)
        direct = sum(1 for e in evidence if e.get("support_type") == "direct")
        return f"{len(evidence)} claims, {direct} direct"

    def _stage_related(self) -> str:
        # Optional - skip in MVP
        write_json(self.paths.related, [])
        return "skipped (not implemented)"

    def _stage_report(self) -> str:
        from paper_agent.extraction.paper_schema import PaperSchema
        from paper_agent.report.writer import generate_report
        from paper_agent.llm.client import LLMClient
        from paper_agent.utils.io import write_text

        chunks = read_jsonl(self.paths.chunks)
        schema_data = read_json(self.paths.paper_schema)
        schema = PaperSchema.from_dict(schema_data)
        evidence = read_json(self.paths.evidence)

        llm = LLMClient(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )

        templates = [self.config.template]
        if "summary" not in templates:
            templates.append("summary")  # always generate summary

        generated = []
        for tmpl in templates:
            report_md = generate_report(schema, evidence, chunks, llm, template=tmpl)
            out_path = self.paths.report(tmpl.replace("-", "_"))
            write_text(out_path, report_md)
            generated.append(tmpl)

        return ", ".join(generated)
