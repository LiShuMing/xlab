"""Investment analysis service wrapper for the unified backend."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from typing import Any

from backend.settings import Settings


def ensure_py_invest_importable(settings: Settings) -> None:
    py_invest_dir = settings.xlab_root / "python" / "projects" / "py-invest"
    if py_invest_dir.exists() and str(py_invest_dir) not in sys.path:
        sys.path.insert(0, str(py_invest_dir))


def status() -> dict[str, Any]:
    return {
        "auto_analysis": False,
        "queue_size": 0,
    }


def get_cached_report(settings: Settings, stock_code: str, mode: str) -> dict[str, Any] | None:
    ensure_py_invest_importable(settings)

    try:
        from storage import get_report, init_db

        init_db()
        cached = get_report(stock_code, date.today())
        if not cached:
            return None

        data = json.loads(cached.analysis_json)
        if data.get("mode") != mode:
            return None
        markdown = data.get("markdown")
        if not markdown:
            return None
        return {
            "stock": data.get("stock_code", stock_code),
            "name": data.get("stock_name", ""),
            "rating": data.get("rating", ""),
            "confidence": data.get("confidence", ""),
            "target_price": data.get("target_price"),
            "duration": data.get("analysis_duration", 0),
            "mode": mode,
            "markdown": markdown,
        }
    except Exception:
        return None


async def analyze_stock(
    settings: Settings,
    *,
    stock_code: str,
    query: str,
    lang: str,
    mode: str,
) -> dict[str, Any]:
    ensure_py_invest_importable(settings)

    from agents.orchestrator import SimpleAgentOrchestrator
    from modules.report_generator.formatter import ReportFormat, ReportFormatter
    from storage import init_db, save_report

    started_at = datetime.now()
    orchestrator = SimpleAgentOrchestrator(lang=lang)
    state = await orchestrator.analyze(stock_code, query, mode=mode)

    if state.error:
        raise RuntimeError(state.error)
    if not state.report:
        raise RuntimeError("No report generated")

    markdown = ReportFormatter.format(state.report, ReportFormat.MARKDOWN, lang=lang)
    report_json = json.loads(ReportFormatter.format(state.report, ReportFormat.JSON, lang=lang))
    report_json["markdown"] = markdown
    report_json["mode"] = mode
    init_db()
    save_report(
        stock_code=state.report.stock_code or stock_code,
        report_date=date.today(),
        analysis_json=json.dumps(report_json, ensure_ascii=False),
    )
    return {
        "stock": state.report.stock_code or stock_code,
        "name": state.report.stock_name,
        "rating": state.report.rating,
        "confidence": state.report.confidence,
        "target_price": state.report.target_price,
        "duration": round((datetime.now() - started_at).total_seconds(), 2),
        "mode": mode,
        "cached": False,
        "markdown": markdown,
    }
