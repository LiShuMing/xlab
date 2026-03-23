"""Web server for DB Radar - serves the latest news as a web page."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, send_from_directory

from dbradar.config import get_config

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")


def get_latest_report() -> Optional[Dict[str, Any]]:
    """Load the latest JSON report from output directory."""
    config = get_config()
    output_dir = config.output_dir

    # Find the latest JSON file (excluding fetched_items.json)
    json_files = sorted(
        [f for f in output_dir.glob("*.json") if f.name != "fetched_items.json"],
        key=lambda f: f.stem,
        reverse=True,
    )

    if not json_files:
        return None

    try:
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        data["_file_date"] = json_files[0].stem
        return data
    except (json.JSONDecodeError, IOError):
        return None


def get_historical_reports(days: int = 7) -> List[Dict[str, Any]]:
    """Load historical reports for the past N days."""
    config = get_config()
    output_dir = config.output_dir

    reports = []
    json_files = sorted(
        [f for f in output_dir.glob("*.json") if f.name != "fetched_items.json"],
        key=lambda f: f.stem,
        reverse=True,
    )[:days]

    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            data["_file_date"] = json_file.stem
            reports.append(data)
        except (json.JSONDecodeError, IOError):
            continue

    return reports


def transform_to_news_items(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform report data to news item format for the frontend."""
    news_items = []
    top_updates = report.get("top_updates", [])

    for idx, update in enumerate(top_updates, 1):
        item = {
            "id": idx,
            "title": update.get("title", "Untitled"),
            "url": update.get("sources", ["#"])[0] if update.get("sources") else "#",
            "site": extract_domain(update.get("sources", [""])[0]) if update.get("sources") else "unknown",
            "source": update.get("product", "Unknown"),
            "product": update.get("product", "Unknown"),
            "points": 100 - (idx - 1) * 5,  # Simulated points based on ranking
            "time": report.get("_file_date", "today"),
            "summary": " ".join(update.get("what_changed", [])),
            "why_it_matters": update.get("why_it_matters", []),
            "what_changed": update.get("what_changed", []),
            "tags": extract_tags(update),
        }
        news_items.append(item)

    return news_items


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return "unknown"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "") or "unknown"
    except Exception:
        return "unknown"


def extract_tags(update: Dict[str, Any]) -> List[str]:
    """Extract relevant tags from update."""
    tags = []
    product = update.get("product", "")
    if product:
        tags.append(product)

    title = update.get("title", "").lower()
    tag_keywords = [
        ("PostgreSQL", ["postgres", "postgresql", "pg_"]),
        ("MySQL", ["mysql", "mariadb"]),
        ("ClickHouse", ["clickhouse"]),
        ("Snowflake", ["snowflake"]),
        ("Databricks", ["databricks"]),
        ("MongoDB", ["mongodb", "mongo"]),
        ("Redis", ["redis"]),
        ("Performance", ["performance", "optimization", "benchmark"]),
        ("Distributed", ["distributed", "cluster", "sharding"]),
        ("OLAP", ["olap", "analytics", "column"]),
        ("AI/ML", ["ai", "machine learning", "ml", "llm", "vector"]),
    ]

    for tag, keywords in tag_keywords:
        if any(kw in title for kw in keywords):
            tags.append(tag)

    return list(set(tags))[:4]  # Max 4 tags


@app.route("/")
def index():
    """Serve the main news page."""
    report = get_latest_report()

    if not report:
        return render_template(
            "index.html",
            news_items=[],
            report_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            executive_summary=["No reports available. Run 'dbradar run' first."],
            themes=[],
            action_items=[],
            intelligence=None,
            error="No data available",
        )

    news_items = transform_to_news_items(report)
    intelligence = report.get("intelligence", {})

    return render_template(
        "index.html",
        news_items=news_items,
        report_date=report.get("_file_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        executive_summary=report.get("executive_summary", []),
        themes=report.get("themes", []),
        action_items=report.get("action_items", []),
        intelligence=intelligence,
        fetch_failures=report.get("fetch_failures", []),
    )


@app.route("/api/news")
def api_news():
    """API endpoint to get news items as JSON."""
    report = get_latest_report()

    if not report:
        return jsonify({"error": "No reports available", "news_items": []})

    news_items = transform_to_news_items(report)
    return jsonify({
        "date": report.get("_file_date"),
        "news_items": news_items,
        "executive_summary": report.get("executive_summary", []),
        "themes": report.get("themes", []),
        "action_items": report.get("action_items", []),
        "intelligence": report.get("intelligence"),
    })


@app.route("/api/history")
def api_history():
    """API endpoint to get historical reports."""
    days = 7
    reports = get_historical_reports(days)
    return jsonify({
        "reports": [
            {
                "date": r.get("_file_date"),
                "themes": r.get("themes", []),
                "top_updates_count": len(r.get("top_updates", [])),
            }
            for r in reports
        ]
    })


@app.route("/api/report/<date>")
def api_report(date: str):
    """API endpoint to get a specific report by date."""
    config = get_config()
    output_dir = config.output_dir
    report_file = output_dir / f"{date}.json"

    if not report_file.exists():
        return jsonify({"error": f"Report not found: {date}"}), 404

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
        return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid report file"}), 500


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the web server."""
    print(f"Starting DB Radar web server at http://{host}:{port}")
    print("Press Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)