"""Investment analysis service wrapper for the unified backend."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.invest import service as invest_repo
from backend.invest import workspace as invest_workspace
from backend.settings import Settings


def status() -> dict[str, Any]:
    return {
        "auto_analysis": False,
        "queue_size": 0,
    }


def list_configured_stocks(settings: Settings) -> dict[str, Any]:
    """Return stock definitions from the static Invest config."""
    stocks = _configured_stocks(settings)
    return {
        "stocks": [
            {
                "code": stock["code"],
                "name": stock["name"] or stock["code"],
                "active": True,
            }
            for stock in stocks
        ]
    }


async def list_stocks(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    stocks = await invest_repo.get_active_stocks(session)
    if not stocks:
        await _sync_configured_stocks(session, settings)
        stocks = await invest_repo.get_active_stocks(session)

    return {
        "stocks": [
            {
                "code": stock.stock_code,
                "name": stock.stock_name or stock.stock_code,
                "active": stock.is_active,
            }
            for stock in stocks
        ]
    }


async def list_reports(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    _ = settings
    reports = []
    for report in await invest_repo.get_latest_reports(session):
        try:
            data = json.loads(report.analysis_json)
        except json.JSONDecodeError:
            continue
        reports.append(format_dashboard_report(data))
    return {"reports": reports}


async def get_dashboard_report(
    session: AsyncSession,
    settings: Settings,
    stock_code: str,
) -> dict[str, Any]:
    _ = settings
    report = await invest_repo.get_latest_report(session, stock_code)
    if not report:
        return {"error": "Report not found"}

    try:
        data = json.loads(report.analysis_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid report JSON: {exc}"}
    return {"report": format_dashboard_report(data)}


async def delete_reports(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    _ = settings
    count = await invest_repo.delete_all_reports(session)
    return {"success": True, "deleted": count}


async def get_cached_report(
    session: AsyncSession,
    settings: Settings,
    stock_code: str,
    mode: str,
) -> dict[str, Any] | None:
    _ = settings
    cached = await invest_repo.get_report(session, stock_code, date.today())
    if not cached:
        return None

    try:
        data = json.loads(cached.analysis_json)
    except json.JSONDecodeError:
        return None
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


async def get_workspace_snapshot(session: AsyncSession, stock_code: str) -> dict[str, Any]:
    thesis = await invest_workspace.get_thesis(session, stock_code)
    if thesis is None:
        return {
            "thesis": None,
            "watch_items": [],
            "journal_entries": [],
            "reviews": [],
        }
    watch_items = await invest_workspace.list_watch_items(session, stock_code)
    journal_entries = await invest_workspace.list_journal_entries(session, stock_code, limit=10)
    reviews = await invest_workspace.list_reviews(session, stock_code, limit=5)
    return {
        "thesis": invest_workspace.serialize_thesis(thesis),
        "watch_items": [invest_workspace.serialize_watch_item(row) for row in watch_items],
        "journal_entries": [invest_workspace.serialize_journal_entry(row) for row in journal_entries],
        "reviews": [invest_workspace.serialize_review(row) for row in reviews],
    }


async def _sync_configured_stocks(session: AsyncSession, settings: Settings) -> int:
    stocks = _configured_stocks(settings)
    if not stocks:
        return 0
    return await invest_repo.sync_stock_configs(session, stocks)


def _configured_stocks(settings: Settings) -> list[dict[str, str]]:
    try:
        from backend.invest.config import ConfigError, load_config

        config = load_config(settings.invest_config_path)
    except ConfigError:
        return []

    stocks = [{"code": stock.code, "name": stock.name} for stock in config.stocks if stock.code]
    return stocks


def _extract_section(data: dict[str, Any], keyword: str) -> str:
    sections = data.get("sections", [])
    if not isinstance(sections, list):
        return ""
    for section in sections:
        if isinstance(section, dict) and keyword in str(section.get("title", "")):
            return str(section.get("content", ""))
    return ""


def format_dashboard_report(data: dict[str, Any]) -> dict[str, Any]:
    """Format stored report JSON for the legacy dashboard shape."""
    raw_data = data.get("raw_data", {})
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    price_data = raw_data.get("query_stock_price", {})
    metrics_data = raw_data.get("query_financial_metrics", {})
    kline_data = raw_data.get("query_kline_data", {})
    price_data = price_data if isinstance(price_data, dict) else {}
    metrics_data = metrics_data if isinstance(metrics_data, dict) else {}
    kline_data = kline_data if isinstance(kline_data, dict) else {}

    price = price_data.get("current_price", 0)
    change = price_data.get("change", 0)
    change_percent = price_data.get("change_percent", 0)

    if not price and kline_data.get("data"):
        kline = kline_data["data"]
        if isinstance(kline, list) and kline:
            last_day = kline[-1]
            if isinstance(last_day, dict):
                price = last_day.get("close", 0)

    sections = data.get("sections", [])
    section_dict = {
        str(section.get("title", "")): str(section.get("content", ""))
        for section in sections
        if isinstance(section, dict)
    }
    technical = _extract_section(data, "技术分析") or section_dict.get("Technical Picture", "")
    fundamental = _extract_section(data, "基本面分析") or section_dict.get("Fundamental Analysis", "")
    risk = _extract_section(data, "风险") or section_dict.get("Risk Factors", "")
    sector = _extract_section(data, "行业") or section_dict.get("Sector & Comparables", "")

    return {
        "code": data.get("stock_code", ""),
        "name": data.get("stock_name", ""),
        "price": price,
        "change": change,
        "changePercent": change_percent,
        "rating": str(data.get("rating", "hold")).lower(),
        "confidence": str(data.get("confidence", "medium")).lower(),
        "targetPrice": data.get("target_price", 0),
        "summary": data.get("summary", ""),
        "metrics": {
            "pe": metrics_data.get("pe_ratio", "-"),
            "pb": metrics_data.get("pb_ratio", "-"),
            "marketCap": metrics_data.get("market_cap", "-"),
            "dividendYield": metrics_data.get("dividend_yield", "-"),
        },
        "analysis": {
            "technical": technical,
            "fundamental": fundamental,
            "risk": risk,
            "sector": sector,
        },
        "scenarios": {
            "bull": data.get("bull_case", ""),
            "bear": data.get("bear_case", ""),
            "base": data.get("base_case", ""),
        },
    }


async def analyze_stock(
    session: AsyncSession,
    settings: Settings,
    *,
    stock_code: str,
    query: str,
    lang: str,
    mode: str,
) -> dict[str, Any]:
    _ = settings
    from backend.invest.agents.orchestrator import SimpleAgentOrchestrator
    from backend.invest.modules.report_generator.formatter import ReportFormat, ReportFormatter

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
    report_id = await invest_repo.save_report(
        session,
        stock_code=state.report.stock_code or stock_code,
        report_date=date.today(),
        analysis_json=json.dumps(report_json, ensure_ascii=False),
    )
    thesis = await invest_workspace.upsert_thesis_from_report(
        session,
        report_id=report_id,
        report_data=report_json,
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
        "thesis": invest_workspace.serialize_thesis(thesis),
    }
