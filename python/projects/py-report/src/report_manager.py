"""Report manager: CRUD operations and manifest management for generated reports."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import structlog

from .exceptions import ReportManagerError

log = structlog.get_logger()

REPORTS_DIR = Path("reports")
DOCS_DIR = Path("docs")
INDEX_FILE = REPORTS_DIR / "index.json"


def _ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    stylesheets = DOCS_DIR / "stylesheets"
    stylesheets.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    if not INDEX_FILE.exists():
        return {"reports": []}
    with INDEX_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: dict) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def slugify(name: str) -> str:
    """Convert product name to a URL/filename-safe slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug.strip("-")


def save_report(product_name: str, content: str) -> Path:
    """Persist a report to disk and update the manifest."""
    _ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(product_name)
    filename = f"{slug}_{ts}.md"
    report_path = REPORTS_DIR / filename

    try:
        with report_path.open("w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        raise ReportManagerError(f"Failed to write report: {exc}") from exc

    # update index
    index = _load_index()
    entry = {
        "product": product_name,
        "slug": slug,
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "path": str(report_path),
    }
    index["reports"].append(entry)
    _save_index(index)

    # update docs/index.md with the latest report
    docs_index = DOCS_DIR / "index.md"
    try:
        shutil.copy2(report_path, docs_index)
    except OSError as exc:
        log.warning("docs_index_copy_failed", error=str(exc))

    log.info("report_saved", product=product_name, path=str(report_path))
    return report_path


def list_reports() -> list[dict]:
    """Return all reports from the manifest."""
    return _load_index().get("reports", [])


def get_latest_report(product_name: str | None = None) -> dict | None:
    """Return the latest report entry, optionally filtered by product name."""
    reports = list_reports()
    if product_name:
        slug = slugify(product_name)
        reports = [r for r in reports if r.get("slug") == slug]
    return reports[-1] if reports else None


def delete_report(filename: str) -> bool:
    """Delete a report file and remove it from the manifest."""
    index = _load_index()
    before = len(index["reports"])
    index["reports"] = [r for r in index["reports"] if r.get("filename") != filename]
    if len(index["reports"]) == before:
        return False
    report_path = REPORTS_DIR / filename
    if report_path.exists():
        report_path.unlink()
    _save_index(index)
    log.info("report_deleted", filename=filename)
    return True
