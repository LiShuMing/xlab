"""Web server for DB Radar - serves the latest news as a web page."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, abort, jsonify, render_template, request

from dbradar.config import get_config

# 使用绝对路径
_TEMPLATE_DIR = Path(__file__).parent / "web" / "templates"
_STATIC_DIR = Path(__file__).parent / "web" / "static"

app = Flask(__name__, template_folder=str(_TEMPLATE_DIR), static_folder=str(_STATIC_DIR))

# 每页显示的条目数（按条目分页，保证每页数量一致）
ITEMS_PER_PAGE = 30

# 视图模式: 'pagination' (分页) 或 'waterfall' (瀑布流)
DEFAULT_VIEW_MODE = "pagination"


def get_available_dates() -> List[str]:
    """Get list of available report dates."""
    config = get_config()
    output_dir = config.output_dir

    json_files = sorted(
        [f for f in output_dir.glob("*.json") if f.name != "fetched_items.json"],
        key=lambda f: f.stem,
        reverse=True,
    )

    return [f.stem for f in json_files]


def get_report_by_date(date: str) -> Optional[Dict[str, Any]]:
    """Load a specific report by date."""
    config = get_config()
    output_dir = config.output_dir
    report_file = output_dir / f"{date}.json"

    if not report_file.exists():
        return None

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
        data["_file_date"] = date
        return data
    except (json.JSONDecodeError, IOError):
        return None


def get_latest_report() -> Optional[Dict[str, Any]]:
    """Load the latest JSON report from output directory."""
    dates = get_available_dates()
    if not dates:
        return None
    return get_report_by_date(dates[0])


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "") or ""
    except Exception:
        return ""


def transform_to_news_items(report: Dict[str, Any], max_summary_length: int = 600) -> List[Dict[str, Any]]:
    """Transform report data to news item format.

    Args:
        report: Report dictionary with top_updates.
        max_summary_length: Maximum characters for summary (default 600).

    Returns:
        List of news items with title, original_title, summary, tags, etc.
    """
    news_items = []
    top_updates = report.get("top_updates", [])

    for idx, update in enumerate(top_updates, 1):
        sources = update.get("sources", [])
        url = sources[0] if sources else ""

        # Build comprehensive summary from all available content
        summary_parts = []

        # 主要变更/内容
        what_changed = update.get("what_changed", [])
        if what_changed:
            summary_parts.extend(what_changed)

        # 为什么重要
        why_it_matters = update.get("why_it_matters", [])
        if why_it_matters:
            summary_parts.extend(why_it_matters)

        # 证据/细节
        evidence = update.get("evidence", [])
        if evidence:
            summary_parts.extend(evidence[:2])  # 最多2条证据

        summary = "；".join(summary_parts) if summary_parts else ""
        if len(summary) > max_summary_length:
            summary = summary[:max_summary_length - 3] + "..."

        # Get other sources (excluding primary)
        other_sources = []
        for src in sources[1:]:
            domain = extract_domain(src)
            if domain:
                other_sources.append({"url": src, "site": domain})

        # Extract tags from content
        tags = extract_tags(update)

        item = {
            "id": idx,
            "title": update.get("title", "Untitled"),
            "original_title": update.get("original_title", update.get("title", "Untitled")),
            "url": url,
            "site": extract_domain(url),
            "product": update.get("product", ""),
            "summary": summary,
            "tags": tags,
            "other_sources": other_sources,
            "published_date": format_date(update.get("published_date", "")),
            "content_type": update.get("content_type", "blog"),
            "content_type_cn": CONTENT_TYPE_LABELS.get(update.get("content_type", "blog"), "文章"),
        }
        news_items.append(item)

    return news_items


def format_date(date_str: str) -> str:
    """Format date string for display."""
    if not date_str:
        return ""

    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        # Ensure both datetimes are offset-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        diff_days = (now - dt).days

        if diff_days == 0:
            return "今天"
        elif diff_days == 1:
            return "昨天"
        elif diff_days < 7:
            return f"{diff_days}天前"
        else:
            return dt.strftime("%m-%d")
    except (ValueError, AttributeError):
        return ""


CONTENT_TYPE_LABELS = {
    "release": "发布",
    "benchmark": "基准测试",
    "blog": "博客",
    "news": "新闻",
    "tutorial": "教程",
    "other": "文章",
}


def format_date_display(date_str: str) -> str:
    """Format date for display header.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Human readable date like "3月24日 周一" or "今天".
    """
    if not date_str:
        return ""

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now().date()
        date_obj = dt.date()

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        if date_obj == today:
            return "今天"
        elif date_obj == today - timedelta(days=1):
            return "昨天"
        else:
            weekday = weekdays[dt.weekday()]
            return f"{dt.month}月{dt.day}日 {weekday}"
    except (ValueError, AttributeError):
        return date_str


from datetime import timedelta


def extract_tags(update: Dict[str, Any]) -> List[str]:
    """Extract relevant tags from update content."""
    tags = []
    title = update.get("title", "").lower()
    what_changed = " ".join(update.get("what_changed", [])).lower()
    why_matters = " ".join(update.get("why_it_matters", [])).lower()
    combined = f"{title} {what_changed} {why_matters}"

    tag_keywords = [
        ("Parquet", ["parquet"]),
        ("OLAP", ["olap", "analytics", "列式", "column"]),
        ("迁移", ["迁移", "migration", "migrate"]),
        ("性能", ["performance", "性能", "benchmark", "基准"]),
        ("分布式", ["distributed", "分布式", "cluster"]),
        ("复制", ["replication", "复制", "binlog"]),
        ("存储", ["storage", "存储", "引擎"]),
        ("压缩", ["compression", "压缩"]),
        ("OLTP", ["oltp", "事务"]),
        ("Iceberg", ["iceberg"]),
        ("AI/ML", ["ai", "ml", "llm", "vector", "机器学习"]),
    ]

    for tag, keywords in tag_keywords:
        if any(kw in combined for kw in keywords):
            tags.append(tag)

    return tags[:4]  # Max 4 tags


def get_all_items_with_dates() -> List[Dict[str, Any]]:
    """Get all news items with date info, flattened and sorted by date."""
    dates = get_available_dates()
    all_items = []

    for date in dates:
        report = get_report_by_date(date)
        if report:
            news_items = transform_to_news_items(report)
            for item in news_items:
                item['_date'] = date
                item['_date_display'] = format_date_display(date)
            all_items.extend(news_items)

    return all_items


@app.route("/")
def index():
    """Serve the main news page."""
    return show_page(1)


@app.route("/page/<int:page>")
def show_page(page: int):
    """Show a specific page of news (each page = ITEMS_PER_PAGE items).

    Items are grouped by date for display, but pagination is based on item count.
    """
    if page < 1:
        page = 1

    all_items = get_all_items_with_dates()

    if not all_items:
        return render_template(
            "index.html",
            date_groups=[],
            current_page=page,
            total_pages=0,
            has_prev=False,
            has_next=False,
            total_items=0,
            error="暂无数据。请先运行 dbradar run 生成报告。",
        )

    # Calculate pagination based on items
    total_items = len(all_items)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    # Ensure page is within bounds
    if page > total_pages:
        page = total_pages if total_pages > 0 else 1

    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
    page_items = all_items[start_idx:end_idx]

    # Update item IDs to be sequential across pages
    for idx, item in enumerate(page_items, start=start_idx + 1):
        item['id'] = idx

    # Group items by date for display
    date_groups = []
    current_date = None
    current_items = []

    for item in page_items:
        item_date = item['_date']
        if item_date != current_date:
            if current_items:
                date_groups.append({
                    "date": current_date,
                    "date_display": format_date_display(current_date),
                    "news_items": current_items,
                    "total": len(current_items),
                })
            current_date = item_date
            current_items = []
        current_items.append(item)

    # Add the last group
    if current_items:
        date_groups.append({
            "date": current_date,
            "date_display": format_date_display(current_date),
            "news_items": current_items,
            "total": len(current_items),
        })

    return render_template(
        "index.html",
        date_groups=date_groups,
        current_page=page,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
        prev_page=page - 1 if page > 1 else None,
        next_page=page + 1 if page < total_pages else None,
        total_items=total_items,
        items_per_page=ITEMS_PER_PAGE,
    )


@app.route("/date/<date>")
def by_date(date: str):
    """Serve a specific date's report."""
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        abort(404)

    report = get_report_by_date(date)
    if not report:
        abort(404)

    news_items = transform_to_news_items(report)

    # Add date info to items
    for item in news_items:
        item['_date'] = date
        item['_date_display'] = format_date_display(date)

    # Single date group
    date_groups = [{
        "date": date,
        "date_display": format_date_display(date),
        "news_items": news_items,
        "total": len(news_items),
    }]

    return render_template(
        "index.html",
        date_groups=date_groups,
        current_page=1,
        total_pages=1,
        has_prev=False,
        has_next=False,
        total_items=len(news_items),
        items_per_page=ITEMS_PER_PAGE,
        single_date=True,
    )


@app.route("/api/news")
def api_news():
    """API endpoint to get news items as JSON."""
    report = get_latest_report()
    if not report:
        return jsonify({"error": "No reports available", "news_items": []})

    news_items = transform_to_news_items(report)
    return jsonify(
        {
            "date": report.get("_file_date"),
            "news_items": news_items,
            "executive_summary": report.get("executive_summary", []),
        }
    )


@app.route("/api/dates")
def api_dates():
    """API endpoint to get available dates."""
    return jsonify({"dates": get_available_dates()})


@app.route("/api/report/<date>")
def api_report(date: str):
    """API endpoint to get a specific report by date."""
    report = get_report_by_date(date)
    if not report:
        return jsonify({"error": f"Report not found: {date}"}), 404
    return jsonify(report)


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the web server."""
    print(f"Starting DB Radar web server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)