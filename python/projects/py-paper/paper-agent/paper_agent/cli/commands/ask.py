"""ask command: question answering with citations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from paper_agent.core.paths import RunPaths
from paper_agent.llm.client import LLMClient
from paper_agent.qa.answerer import answer_question
from paper_agent.qa.retriever import retrieve_chunks
from paper_agent.utils.io import read_json, read_jsonl
from paper_agent.utils.logging import configure_logging, set_correlation_id

console = Console()


def register(app: typer.Typer) -> None:
    """Register the ask command with the CLI app."""

    @app.command()
    def ask(
        run_dir: Path = typer.Argument(..., help="Path to run directory"),
        question: str = typer.Option(..., "--question", "-q", help="Question to ask"),
        top_k: int = typer.Option(6, "--top-k", help="Number of chunks to retrieve"),
        model: str | None = typer.Option(None, "--model"),
        format: str = typer.Option("md", "--format", help="Output format: md | plain"),
        verbose: bool = typer.Option(False, "--verbose", "-v"),
        debug: bool = typer.Option(False, "--debug"),
    ) -> None:
        """Ask a question about an analyzed paper with citations."""
        set_correlation_id()
        configure_logging(verbose=verbose, debug=debug)

        paths = RunPaths(run_dir)

        if not paths.chunks.exists():
            console.print(
                f"[red]Error:[/red] No chunks found in {run_dir}. Run analyze first."
            )
            raise typer.Exit(1)

        if not paths.paper_schema.exists():
            console.print(
                "[red]Error:[/red] No paper schema found. Run analyze first."
            )
            raise typer.Exit(1)

        chunks = read_jsonl(paths.chunks)
        schema_data = read_json(paths.paper_schema)
        evidence = read_json(paths.evidence) if paths.evidence.exists() else []

        # Load config if available
        cfg_data = read_json(paths.config) if paths.config.exists() else {}
        resolved_model = model or cfg_data.get("model", "qwen3.5-plus")
        timeout = cfg_data.get("timeout", 300)

        llm = LLMClient(
            model=resolved_model, max_tokens=2048, temperature=0.1, timeout=timeout
        )

        console.print(f"[blue]Question:[/blue] {question}")
        console.print(f"[dim]Retrieving top {top_k} chunks...[/dim]")

        relevant_chunks = retrieve_chunks(question, chunks, top_k=top_k)

        console.print("[dim]Generating answer...[/dim]")
        result = answer_question(question, relevant_chunks, schema_data, evidence, llm)

        if format == "md":
            console.print(Markdown(result["answer"]))
        else:
            console.print(result["answer"])

        if result.get("citations"):
            console.print("\n[bold]Citations:[/bold]")
            for cit in result["citations"]:
                pages = ", ".join(f"p{p}" for p in cit.get("pages", []))
                section = cit.get("section", "")
                chunk_id = cit.get("chunk_id", "")[:8]
                console.print(f"  [dim][{chunk_id}] {section} {pages}[/dim]")
