"""FastAPI server: exposes refresh endpoint and serves MkDocs output."""
from __future__ import annotations

import subprocess
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .exceptions import MkDocsError, ResearcherError
from .report_manager import list_reports
from .researcher import generate_report_async
from .report_manager import save_report

log = structlog.get_logger()

SITE_DIR = Path("site")
MKDOCS_BIN = "/home/lism/env/venv/bin/mkdocs"

app = FastAPI(title="LLM API Deep Research Hub", version="0.1.0")


def _build_mkdocs() -> None:
    result = subprocess.run(
        [MKDOCS_BIN, "build", "--clean"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MkDocsError(f"MkDocs build failed:\n{result.stderr}")
    log.info("mkdocs_built")


@app.get("/refresh")
async def refresh(
    product: str = Query(..., description="LLM API product name to research"),
    language: str = Query("English", description="Report language"),
    depth: str = Query("deep", description="Research depth: standard | deep | executive"),
) -> JSONResponse:
    """Trigger a new research call and rebuild MkDocs."""
    try:
        content = await generate_report_async(product, language, depth)
        report_path = save_report(product, content)
        _build_mkdocs()
    except ResearcherError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MkDocsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"status": "ok", "report": str(report_path)})


@app.get("/reports")
async def reports() -> JSONResponse:
    """List all available reports."""
    return JSONResponse({"reports": list_reports()})


# Serve MkDocs site if built
if SITE_DIR.exists():
    app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")
else:

    @app.get("/")
    async def root() -> JSONResponse:
        return JSONResponse({"message": "MkDocs site not built yet. Run `make build` first."})
