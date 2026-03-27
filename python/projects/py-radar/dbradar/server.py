"""Web server for DB Radar - serves the latest news as a web page.

This version uses DuckDB for efficient storage and querying.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from flask import Flask, abort, jsonify, render_template, request

from dbradar.config import get_config
from dbradar.storage import DuckDBStore, StorageItem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 使用绝对路径
_TEMPLATE_DIR = Path(__file__).parent / "web" / "templates"
_STATIC_DIR = Path(__file__).parent / "web" / "static"

app = Flask(__name__, template_folder=str(_TEMPLATE_DIR), static_folder=str(_STATIC_DIR))

# 每页显示的条目数
ITEMS_PER_PAGE = 30

# Global store instance (initialized on first use)
_store: Optional[DuckDBStore] = None

# Background task control
_background_task: Optional[threading.Thread] = None
_background_task_running = False
_summary_executor: Optional[ThreadPoolExecutor] = None


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
        "_date": item.sync_batch.isoformat() if item.sync_batch else (item.published_date.isoformat() if item.published_date else ""),
        "_date_display": format_sync_batch_display(item.sync_batch),
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


def format_sync_batch_display(sync_batch: Optional[date]) -> str:
    """Format sync_batch for display header (shows as 'Added on YYYY-MM-DD')."""
    if not sync_batch:
        return "未知时间"

    try:
        today = date.today()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        if sync_batch == today:
            return "今天新增"
        elif sync_batch == today - timedelta(days=1):
            return "昨天新增"
        else:
            weekday = weekdays[sync_batch.weekday()]
            return f"{sync_batch.month}月{sync_batch.day}日 {weekday} 新增"
    except (ValueError, AttributeError):
        return str(sync_batch)


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

    # Query items for this page, ordered by sync_batch
    items = store.query_by_sync_batch(limit=ITEMS_PER_PAGE, offset=start_idx)

    # Convert to dicts and assign sequential IDs
    item_dicts = []
    for idx, item in enumerate(items, start=start_idx + 1):
        d = storage_item_to_dict(item, idx)
        item_dicts.append(d)

    # Group by sync_batch (not published_date)
    date_groups = group_items_by_sync_batch(item_dicts)

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


def group_items_by_sync_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group items by sync_batch for display."""
    date_groups = []
    current_batch = None
    current_items = []

    for item in items:
        item_batch = item.get("_date", "")
        if item_batch != current_batch:
            if current_items:
                date_groups.append({
                    "date": current_batch,
                    "date_display": current_items[0].get("_date_display", ""),
                    "news_items": current_items,
                    "total": len(current_items),
                })
            current_batch = item_batch
            current_items = []
        current_items.append(item)

    # Add last group
    if current_items:
        date_groups.append({
            "date": current_batch,
            "date_display": current_items[0].get("_date_display", ""),
            "news_items": current_items,
            "total": len(current_items),
        })

    return date_groups


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
    """Serve a specific sync_batch's items."""
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        abort(404)

    store = get_store()

    # Query items by sync_batch instead of published_date
    conn = store._get_conn()
    rows = conn.execute("""
        SELECT * FROM items WHERE sync_batch = ?
        ORDER BY published_date DESC
    """, [target_date]).fetchall()
    items = [store._row_to_item(row) for row in rows]

    if not items:
        abort(404)

    item_dicts = [storage_item_to_dict(item, idx + 1) for idx, item in enumerate(items)]

    date_groups = [{
        "date": date_str,
        "date_display": format_sync_batch_display(target_date),
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


@app.route("/api/item/<int:item_id>/summary")
def api_item_summary(item_id: int):
    """API endpoint to get summary for a specific item by its display ID."""
    store = get_store()

    # Get total count to validate ID range
    stats = store.get_stats()
    total_items = stats["total_count"]

    if item_id < 1 or item_id > total_items:
        abort(404)

    # Query the item at the specific offset (item_id is 1-based)
    items = store.query(limit=1, offset=item_id - 1)

    if not items:
        abort(404)

    item = items[0]
    return jsonify({
        "id": item_id,
        "summary": item.summary or "No summary available",
        "title": item.title,
    })


def run_server(
    host: str = "0.0.0.0",
    port: int = 5000,
    debug: bool = False,
    enable_background_tasks: bool = True,
):
    """Run the web server."""
    print(f"Starting DB Radar web server at http://{host}:{port}")
    print(f"Press Ctrl+C to stop")

    # Initialize store
    store = get_store()
    stats = store.get_stats()
    print(f"Storage: {stats['total_count']} items loaded")

    # Start background task for summary generation
    if enable_background_tasks:
        start_background_summary_task()

    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        stop_background_summary_task()
        store.close()


def start_background_summary_task():
    """Start the background task for generating summaries."""
    global _background_task, _background_task_running, _summary_executor

    if _background_task_running:
        logger.info("Background summary task already running")
        return

    _background_task_running = True

    # Create thread pool for summary generation (max 3 concurrent workers)
    _summary_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="summary-gen-")

    _background_task = threading.Thread(target=_background_summary_worker, daemon=True)
    _background_task.start()
    logger.info("Background summary generation task started")


def stop_background_summary_task():
    """Stop the background summary generation task."""
    global _background_task_running, _background_task, _summary_executor

    _background_task_running = False

    if _summary_executor:
        logger.info("Shutting down summary executor...")
        _summary_executor.shutdown(wait=True, cancel_futures=True)
        _summary_executor = None

    if _background_task and _background_task.is_alive():
        logger.info("Waiting for background task to finish...")
        _background_task.join(timeout=10)

    logger.info("Background summary generation task stopped")


def _background_summary_worker():
    """Worker function that runs in background to generate summaries.

    This function runs in a separate thread and periodically checks for
    items without summaries, then submits them to the thread pool for processing.
    """
    global _background_task_running, _summary_executor

    # Wait a bit for server to fully start
    time.sleep(5)

    while _background_task_running:
        try:
            # Check if we should continue
            if not _background_task_running or not _summary_executor:
                break

            # Get items without summary using a fresh connection
            items = _get_items_without_summary()

            if not items:
                logger.debug("No items without summary found, sleeping...")
                time.sleep(60)  # Check again in 1 minute
                continue

            logger.info(f"Found {len(items)} items without summary, submitting to thread pool...")

            # Submit all items to thread pool
            futures = []
            for item in items:
                if not _background_task_running:
                    break
                future = _summary_executor.submit(_generate_summary_worker, item)
                futures.append((future, item))

            # Wait for all to complete with timeout
            for future, item in futures:
                if not _background_task_running:
                    break
                try:
                    future.result(timeout=120)  # 2 minute timeout per item
                except Exception as e:
                    logger.error(f"Error generating summary for {item.id}: {e}")

            # Wait before next batch
            time.sleep(5)

        except Exception as e:
            logger.error(f"Error in background summary worker: {e}")
            time.sleep(30)  # Wait longer on error


def _get_items_without_summary() -> List[StorageItem]:
    """Get items without summary using a separate database connection.

    Each thread needs its own DuckDB connection to avoid lock conflicts.
    """
    try:
        config = get_config()
        store = DuckDBStore(
            data_dir=config.output_dir.parent / "data",
            db_name="items.duckdb",
        )
        items = store.get_items_without_summary(limit=10)
        store.close()
        return items
    except Exception as e:
        logger.error(f"Error getting items without summary: {e}")
        return []


def _generate_summary_worker(item: StorageItem):
    """Worker function to generate summary for a single item.

    This runs in a thread pool worker and creates its own database connection.

    Args:
        item: The StorageItem to generate summary for.
    """
    logger.info(f"Generating summary for item: {item.id} - {item.title[:50]}...")

    try:
        # Generate summary using LLM
        summary = _generate_summary_with_llm(item)

        if summary:
            # Update the item with the new summary using a separate connection
            success = _update_item_summary(item.id, summary)
            if success:
                logger.info(f"Summary generated and saved for {item.id}")
            else:
                logger.error(f"Failed to save summary for {item.id}")
        else:
            logger.warning(f"No summary generated for {item.id}")

    except Exception as e:
        logger.error(f"Error in summary worker for {item.id}: {e}")


def _update_item_summary(item_id: str, summary: str) -> bool:
    """Update item summary using a separate database connection.

    Args:
        item_id: The ID of the item to update.
        summary: The summary text to save.

    Returns:
        True if successful, False otherwise.
    """
    try:
        config = get_config()
        store = DuckDBStore(
            data_dir=config.output_dir.parent / "data",
            db_name="items.duckdb",
        )
        success = store.update_summary(item_id, summary)
        store.close()
        return success
    except Exception as e:
        logger.error(f"Error updating summary for {item_id}: {e}")
        return False


def _generate_summary_with_llm(item: StorageItem) -> Optional[str]:
    """Generate a summary for an item using LLM API.

    Args:
        item: The StorageItem to summarize.

    Returns:
        The generated summary string, or None if generation failed.
    """
    config = get_config()

    # Check if API key is configured
    if not config.api_key:
        logger.warning("No LLM API key configured, skipping summary generation")
        return None

    # Build prompt for single item summary (Chinese, detailed)
    prompt = f"""你是一位技术内容摘要专家。请用中文为以下文章生成一份详细摘要。

## 文章信息

标题: {item.title or item.original_title}
产品: {item.product or 'Unknown'}
内容类型: {item.content_type or 'article'}
URL: {item.url}

## 原始内容

{item.raw_content[:4000] if item.raw_content else '[无原始内容]'}

## 摘要要求

1. 用中文撰写，语言流畅自然
2. 包含以下要素：
   - 文章核心主题（1-2句话）
   - 主要技术点或关键信息（2-3点）
   - 实际意义或应用场景（1-2句话）
3. 摘要长度控制在150-300字之间
4. 使用专业但易懂的技术语言
5. 不要包含markdown格式、标题或项目符号
6. 直接输出摘要正文，不要添加"摘要："等前缀

请生成一份信息丰富、能够帮助读者快速了解文章主旨的详细摘要。"""

    try:
        client = httpx.Client(timeout=config.timeout)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }

        payload = {
            "model": config.model,
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = client.post(
            f"{config.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        # Extract response text
        raw_text = ""
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                raw_text = choice["message"]["content"]

        client.close()

        if raw_text:
            # Clean up the summary
            summary = raw_text.strip()
            # Remove quotes if present
            if summary.startswith('"') and summary.endswith('"'):
                summary = summary[1:-1]
            if summary.startswith("'") and summary.endswith("'"):
                summary = summary[1:-1]
            return summary

        return None

    except Exception as e:
        logger.error(f"LLM API error for item {item.id}: {e}")
        return None


if __name__ == "__main__":
    run_server(debug=True)
