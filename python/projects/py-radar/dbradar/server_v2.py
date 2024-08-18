"""Web server for DB Radar - serves the latest news as a web page.

This version uses DuckDB for efficient storage and querying.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, abort, jsonify, render_template, request

from dbradar.config import get_config
from dbradar.storage import DuckDBStore, StorageItem

# 使用绝对路径
_TEMPLATE_DIR = Path(__file__).parent / "web" / "templates"
_STATIC_DIR = Path(__file__).parent / "web" / "static"

app = Flask(__name__, template_folder=str(_TEMPLATE_DIR), static_folder=str(_STATIC_DIR))

# 每页显示的条目数
ITEMS_PER_PAGE = 30

# Global store instance (initialized on first use)
_store: Optional[DuckDBStore] = None


def get_store() -> DuckDBStore:
    """Get or initialize the DuckDB store."""
    global _store
    if _store is None:
        config = get_config()
        _store = DuckDBStore(
            data_dir=config.output_dir.parent / "data",
            db_name="items.duckdb",
        )
    return _store


def storage_item_to_dict(item: StorageItem, idx: int) -> Dict[str, Any]:
    """Convert StorageItem to template-compatible dict."""
    return {
        "id": idx,
        "title": item.title,
        "original_title": item.original_title or item.title,
        "url": item.url,
        "site": extract_domain(item.url),
        "product": item.product,
        "summary": item.summary,
        "tags": item.tags,
        "other_sources": [{"url": url, "site": extract_domain(url)} for url in item.sources],
        "published_date": format_date(item.published_date),
        "content_type": item.content_type,
        "content_type_cn": CONTENT_TYPE_LABELS.get(item.content_type, "文章"),
        "_date": item.published_date.isoformat() if item.published_date else "",
        "_date_display": format_date_display(item.published_date),
    }


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


def format_date(item_date: Optional[date]) -> str:
    """Format date for display."""
    if not item_date:
        return ""

    try:
        today = date.today()
        diff_days = (today - item_date).days

        if diff_days == 0:
            return "今天"
        elif diff_days == 1:
            return "昨天"
        elif diff_days < 7:
            return f"{diff_days}天前"
        else:
            return item_date.strftime("%m-%d")
    except (ValueError, AttributeError):
        return ""


def format_date_display(item_date: Optional[date]) -> str:
    """Format date for display header."""
    if not item_date:
        return ""

    try:
        today = date.today()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        if item_date == today:
            return "今天"
        elif item_date == today - timedelta(days=1):
            return "昨天"
        else:
            weekday = weekdays[item_date.weekday()]
            return f"{item_date.month}月{item_date.day}日 {weekday}"
    except (ValueError, AttributeError):
        return str(item_date)


CONTENT_TYPE_LABELS = {
    "release": "发布",
    "benchmark": "基准测试",
    "blog": "博客",
    "news": "新闻",
    "tutorial": "教程",
    "other": "文章",
}


@app.route("/")
def index():
    """Serve the main news page."""
    return show_page(1)


@app.route("/page/<int:page>")
def show_page(page: int):
    """Show a specific page of news (each page = ITEMS_PER_PAGE items)."""
    if page < 1:
        page = 1

    store = get_store()

    # Get total count
    stats = store.get_stats()
    total_items = stats["total_count"]

    if total_items == 0:
        return render_template(
            "index.html",
            date_groups=[],
            current_page=page,
            total_pages=0,
            has_prev=False,
            has_next=False,
            total_items=0,
            items_per_page=ITEMS_PER_PAGE,
            error="暂无数据。请先运行 dbradar fetch 获取数据。",
        )

    # Calculate pagination
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * ITEMS_PER_PAGE

    # Query items for this page
    items = store.query(limit=ITEMS_PER_PAGE, offset=start_idx)

    # Convert to dicts and assign sequential IDs
    item_dicts = []
    for idx, item in enumerate(items, start=start_idx + 1):
        d = storage_item_to_dict(item, idx)
        item_dicts.append(d)

    # Group by date
    date_groups = group_items_by_date(item_dicts)

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


def group_items_by_date(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group items by date for display."""
    date_groups = []
    current_date = None
    current_items = []

    for item in items:
        item_date = item.get("_date", "")
        if item_date != current_date:
            if current_items:
                date_groups.append({
                    "date": current_date,
                    "date_display": current_items[0].get("_date_display", ""),
                    "news_items": current_items,
                    "total": len(current_items),
                })
            current_date = item_date
            current_items = []
        current_items.append(item)

    # Add last group
    if current_items:
        date_groups.append({
            "date": current_date,
            "date_display": current_items[0].get("_date_display", ""),
            "news_items": current_items,
            "total": len(current_items),
        })

    return date_groups


@app.route("/date/<date_str>")
def by_date(date_str: str):
    """Serve a specific date's report."""
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    store = get_store()
    items = store.get_by_date(target_date)

    if not items:
        abort(404)

    item_dicts = [storage_item_to_dict(item, idx + 1) for idx, item in enumerate(items)]

    date_groups = [{
        "date": date_str,
        "date_display": format_date_display(target_date),
        "news_items": item_dicts,
        "total": len(item_dicts),
    }]

    return render_template(
        "index.html",
        date_groups=date_groups,
        current_page=1,
        total_pages=1,
        has_prev=False,
        has_next=False,
        total_items=len(item_dicts),
        items_per_page=ITEMS_PER_PAGE,
        single_date=True,
    )


@app.route("/api/news")
def api_news():
    """API endpoint to get latest news items."""
    store = get_store()

    # Get recent 7 days
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    items = store.query(start_date=start_date, end_date=end_date, limit=100)

    return jsonify({
        "items": [item.to_dict() for item in items],
        "count": len(items),
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
    })


@app.route("/api/items")
def api_items():
    """API endpoint to get items with pagination."""
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", ITEMS_PER_PAGE)), 100)

    store = get_store()
    stats = store.get_stats()
    total_items = stats["total_count"]
    total_pages = (total_items + per_page - 1) // per_page

    offset = (page - 1) * per_page
    items = store.query(limit=per_page, offset=offset)

    return jsonify({
        "items": [item.to_dict() for item in items],
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    })


@app.route("/api/stats")
def api_stats():
    """API endpoint to get storage statistics."""
    store = get_store()
    stats = store.get_stats()

    return jsonify({
        "total_count": stats["total_count"],
        "db_size_mb": round(stats["db_size_mb"], 2),
        "db_path": stats["db_path"],
        "date_range": {
            "min": stats["date_range"][0].isoformat() if stats["date_range"][0] else None,
            "max": stats["date_range"][1].isoformat() if stats["date_range"][1] else None,
        },
        "by_content_type": stats["by_content_type"],
    })


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the web server."""
    print(f"Starting DB Radar web server at http://{host}:{port}")
    print(f"Press Ctrl+C to stop")

    # Initialize store
    store = get_store()
    stats = store.get_stats()
    print(f"Storage: {stats['total_count']} items loaded")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        store.close()


if __name__ == "__main__":
    run_server(debug=True)
