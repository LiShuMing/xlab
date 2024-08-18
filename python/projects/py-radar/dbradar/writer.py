"""Write reports to Markdown and JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dbradar.ranker import RankedItem
from dbradar.summarizer import SummaryResult


def detect_content_type(update: Dict[str, Any]) -> str:
    """Detect content type from update data.

    Args:
        update: Update dictionary with title, sources, product, etc.

    Returns:
        Content type string: 'release', 'benchmark', 'blog', 'news', 'tutorial', 'other'
    """
    title = update.get("title", "").lower()
    original_title = update.get("original_title", "").lower()
    sources = update.get("sources", [])
    url = sources[0] if sources else ""
    what_changed = " ".join(update.get("what_changed", [])).lower()

    combined = f"{title} {original_title} {what_changed} {url}".lower()

    # Release notes
    if any(kw in combined for kw in ["release", "version", "v1.", "v2.", "v3.", "发布", "版本更新"]):
        if "/release" in url or "/blog/release" in url or "release_notes" in url:
            return "release"

    # Benchmark
    if any(kw in combined for kw in ["benchmark", "性能测试", "performance test", "吞吐", "latency", "qps", "throughput"]):
        return "benchmark"

    # Tutorial
    if any(kw in combined for kw in ["how to", "tutorial", "guide", "入门", "教程", "指南", "getting started"]):
        return "tutorial"

    # News
    if any(kw in combined for kw in ["announce", "launch", "发布", "announce", "introduc"]):
        return "news"

    # Blog (default for blog domains)
    if "/blog/" in url or "blog." in url:
        return "blog"

    return "other"


if TYPE_CHECKING:
    from dbradar.intelligence.types import CompetitiveInsight, TrendResult
    from dbradar.interests import InterestsConfig


# Translations for UI elements
TRANSLATIONS = {
    "en": {
        "title": "Daily DB Radar - {date}",
        "executive_summary": "Executive Summary",
        "top_updates": "Top Updates",
        "what_changed": "What changed:",
        "why_it_matters": "Why it matters:",
        "sources": "Source(s):",
        "evidence": "Evidence:",
        "release_notes": "Release Notes Tracker",
        "table_product": "Product",
        "table_version": "Version",
        "table_date": "Date",
        "table_highlights": "Highlights",
        "themes": "Themes & Trends",
        "action_items": "Action Items",
        "fetch_failures": "Fetch Failures",
        "table_url": "URL",
        "table_reason": "Reason",
        "generated_at": "Report generated at {time}",
        "date_not_available": "Date not available",
        # Intelligence sections
        "intelligence": "Intelligence Analysis",
        "trend_analysis": "Trend Analysis",
        "emerging_topics": "Emerging Topics",
        "declining_topics": "Declining Topics",
        "recurring_themes": "Recurring Themes",
        "competitive_analysis": "Competitive Analysis",
        "recent_moves": "Recent Moves",
        "positioning_changes": "Positioning Changes",
        "competitive_threats": "Competitive Threats",
        "opportunities": "Opportunities",
    },
    "zh": {
        "title": "每日数据库雷达 - {date}",
        "executive_summary": "执行摘要",
        "top_updates": "重要更新",
        "what_changed": "变更内容：",
        "why_it_matters": "重要性：",
        "sources": "来源：",
        "evidence": "证据：",
        "release_notes": "发布版本追踪",
        "table_product": "产品",
        "table_version": "版本",
        "table_date": "日期",
        "table_highlights": "亮点",
        "themes": "主题与趋势",
        "action_items": "行动项",
        "fetch_failures": "获取失败",
        "table_url": "URL",
        "table_reason": "原因",
        "generated_at": "报告生成时间：{time}",
        "date_not_available": "日期不可用",
        # Intelligence sections
        "intelligence": "情报分析",
        "trend_analysis": "趋势分析",
        "emerging_topics": "新兴话题",
        "declining_topics": "衰退话题",
        "recurring_themes": "持续主题",
        "competitive_analysis": "竞争分析",
        "recent_moves": "近期动向",
        "positioning_changes": "定位变化",
        "competitive_threats": "竞争威胁",
        "opportunities": "机会",
    },
}


@dataclass
class Report:
    """Complete report with metadata."""

    date: str
    title: str
    executive_summary: List[str]
    top_updates: List[Dict[str, Any]]
    release_notes: List[Dict[str, Any]]
    themes: List[str]
    action_items: List[str]
    fetch_failures: List[Dict[str, str]]
    # Intelligence data (optional)
    trends: Optional[TrendResult] = None
    competition: List[CompetitiveInsight] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "date": self.date,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "top_updates": self.top_updates,
            "release_notes": self.release_notes,
            "themes": self.themes,
            "action_items": self.action_items,
            "fetch_failures": self.fetch_failures,
            "metadata": {
                **self.metadata,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Add intelligence data if present
        if self.trends or self.competition:
            result["intelligence"] = {
                "trends": self.trends.to_dict() if self.trends else None,
                "competition": [c.to_dict() for c in self.competition],
            }

        return result


class Writer:
    """Write reports to files."""

    def __init__(self, output_dir: Path, language: str = "en"):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.language = language
        self.t = TRANSLATIONS.get(language, TRANSLATIONS["en"])

    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date for display."""
        if not date_str or date_str == "unknown":
            return self.t["date_not_available"]
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return date_str

    def write_markdown(self, report: Report, filename: Optional[str] = None) -> Path:
        """Write report as Markdown."""
        if not filename:
            filename = f"{report.date}.md"

        path = self.output_dir / filename

        lines = [
            f"# {self.t['title'].format(date=report.date)}",
            "",
            f"## {self.t['executive_summary']}",
            "",
        ]

        for bullet in report.executive_summary:
            lines.append(f"- {bullet}")
        lines.append("")

        if report.top_updates:
            lines.append(f"## {self.t['top_updates']}")
            lines.append("")
            for update in report.top_updates:
                lines.append(f"### [{update['product']}] {update['title']}")
                lines.append("")
                lines.append(f"**{self.t['what_changed']}**")
                for change in update.get("what_changed", []):
                    lines.append(f"- {change}")
                lines.append("")
                lines.append(f"**{self.t['why_it_matters']}**")
                for why in update.get("why_it_matters", []):
                    lines.append(f"- {why}")
                lines.append("")
                lines.append(f"**{self.t['sources']}**")
                for url in update.get("sources", []):
                    lines.append(f"- {url}")
                lines.append("")
                if update.get("evidence"):
                    lines.append(f"**{self.t['evidence']}**")
                    for evidence in update["evidence"]:
                        lines.append(f"> {evidence}")
                    lines.append("")

        if report.release_notes:
            lines.append(f"## {self.t['release_notes']}")
            lines.append("")
            lines.append(
                f"| {self.t['table_product']} | {self.t['table_version']} | "
                f"{self.t['table_date']} | {self.t['table_highlights']} |"
            )
            lines.append("|" + "-" * 10 + "|" + "-" * 10 + "|" + "-" * 8 + "|" + "-" * 12 + "|")
            for rn in report.release_notes:
                highlights = "; ".join(rn.get("highlights", [])[:3])
                lines.append(
                    f"| {rn['product']} | {rn.get('version', '-')} | "
                    f"{self._format_date(rn.get('date'))} | {highlights} |"
                )
            lines.append("")

        if report.themes:
            lines.append(f"## {self.t['themes']}")
            lines.append("")
            for theme in report.themes:
                lines.append(f"- {theme}")
            lines.append("")

        if report.action_items:
            lines.append(f"## {self.t['action_items']}")
            lines.append("")
            for item in report.action_items:
                lines.append(f"- {item}")
            lines.append("")

        # Intelligence sections
        if report.trends or report.competition:
            lines.append(f"## {self.t['intelligence']}")
            lines.append("")

        if report.trends:
            lines.append(f"### {self.t['trend_analysis']}")
            lines.append("")

            if report.trends.emerging_topics:
                lines.append(f"**{self.t['emerging_topics']}:**")
                for topic in report.trends.emerging_topics:
                    lines.append(f"- {topic}")
                lines.append("")

            if report.trends.declining_topics:
                lines.append(f"**{self.t['declining_topics']}:**")
                for topic in report.trends.declining_topics:
                    lines.append(f"- {topic}")
                lines.append("")

            if report.trends.recurring_themes:
                lines.append(f"**{self.t['recurring_themes']}:**")
                for theme in report.trends.recurring_themes:
                    lines.append(f"- {theme}")
                lines.append("")

        if report.competition:
            lines.append(f"### {self.t['competitive_analysis']}")
            lines.append("")
            for insight in report.competition:
                lines.append(f"#### {insight.product}")
                lines.append("")

                if insight.recent_moves:
                    lines.append(f"**{self.t['recent_moves']}:**")
                    for move in insight.recent_moves:
                        lines.append(f"- {move}")
                    lines.append("")

                if insight.positioning_changes:
                    lines.append(f"**{self.t['positioning_changes']}:**")
                    for change in insight.positioning_changes:
                        lines.append(f"- {change}")
                    lines.append("")

                if insight.competitive_threats:
                    lines.append(f"**{self.t['competitive_threats']}:**")
                    for threat in insight.competitive_threats:
                        lines.append(f"- {threat}")
                    lines.append("")

                if insight.opportunities:
                    lines.append(f"**{self.t['opportunities']}:**")
                    for opp in insight.opportunities:
                        lines.append(f"- {opp}")
                    lines.append("")

        if report.fetch_failures:
            lines.append(f"## {self.t['fetch_failures']}")
            lines.append("")
            lines.append(f"| {self.t['table_url']} | {self.t['table_reason']} |")
            lines.append("|" + "-" * 8 + "|" + "-" * 8 + "|")
            for failure in report.fetch_failures:
                lines.append(f"| {failure.get('url', '-')} | {failure.get('reason', '-')} |")
            lines.append("")

        lines.append(f"\n*{self.t['generated_at'].format(time=datetime.now(timezone.utc).isoformat())}*")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_json(self, report: Report, filename: Optional[str] = None) -> Path:
        """Write report as JSON."""
        if not filename:
            filename = f"{report.date}.json"

        path = self.output_dir / filename
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def write_html(
        self,
        report: Report,
        ranked_items: List[RankedItem],
        interests: Optional[InterestsConfig] = None,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Write report as HTML using Jinja2 template.

        Note: Static HTML generation is deprecated. Web display is now handled
        by Flask server (dbradar/server.py) which reads from JSON files directly.
        This method returns None and does not generate HTML files.

        Args:
            report: The Report object containing summary data.
            ranked_items: List of ranked items for score visualization.
            interests: Optional interests config for sidebar display.
            filename: Optional output filename (defaults to {date}.html).

        Returns:
            None (static HTML generation deprecated).
        """
        # Static HTML generation is deprecated - Flask server handles web display
        # by reading from JSON files directly (dbradar/server.py)
        return None

    def write_report(
        self,
        summary: SummaryResult,
        ranked_items: List[RankedItem],
        fetch_failures: List[Dict[str, str]],
        date: Optional[str] = None,
        interests: Optional[InterestsConfig] = None,
        write_html: bool = False,
        trends: Optional[TrendResult] = None,
        competition: Optional[List[CompetitiveInsight]] = None,
    ) -> tuple:
        """
        Write both Markdown and JSON reports.

        Args:
            summary: SummaryResult from summarizer.
            ranked_items: List of ranked items for reference.
            fetch_failures: List of fetch failure records.
            date: Optional date string (YYYY-MM-DD), defaults to today.
            interests: Optional interests config for HTML sidebar.
            write_html: Whether to also generate HTML output.
            trends: Optional TrendResult from trend analysis.
            competition: Optional list of CompetitiveInsight from competition analysis.

        Returns:
            Tuple of (markdown_path, json_path, html_path or None).
        """
        report_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Build URL to original title mapping from ranked_items
        url_to_original = {}
        url_to_date = {}
        for item in ranked_items:
            if item.item.url:
                url_to_original[item.item.url] = item.item.title
                if item.item.published_at:
                    url_to_date[item.item.url] = item.item.published_at

        # Add original_title and published_date to each top_update
        enriched_updates = []
        for update in summary.top_updates:
            enriched = dict(update)
            # Try to find original title and date by URL match
            sources = update.get("sources", [])
            original_title = None
            published_date = None
            for src in sources:
                if src in url_to_original:
                    original_title = url_to_original[src]
                    if src in url_to_date:
                        published_date = url_to_date[src]
                    break
            enriched["original_title"] = original_title or update.get("title", "")
            if published_date:
                enriched["published_date"] = published_date

            # Detect content type
            enriched["content_type"] = detect_content_type(enriched)
            enriched_updates.append(enriched)

        report = Report(
            date=report_date,
            title=self.t["title"].format(date=report_date),
            executive_summary=summary.executive_summary,
            top_updates=enriched_updates,
            release_notes=summary.release_notes,
            themes=summary.themes,
            action_items=summary.action_items,
            fetch_failures=fetch_failures,
            trends=trends,
            competition=competition or [],
            metadata={
                "total_items_collected": len(ranked_items),
                "top_items_count": len(summary.top_updates),
                "language": self.language,
            },
        )

        md_path = self.write_markdown(report)
        json_path = self.write_json(report)

        html_path = None
        if write_html:
            html_path = self.write_html(report, ranked_items, interests)

        return md_path, json_path, html_path


def write_reports(
    summary: SummaryResult,
    ranked_items: List[RankedItem],
    fetch_failures: List[Dict[str, str]],
    output_dir: Path,
    date: Optional[str] = None,
    language: str = "en",
) -> tuple:
    """Convenience function to write reports."""
    writer = Writer(output_dir, language=language)
    return writer.write_report(summary, ranked_items, fetch_failures, date)




def write_html_report(
    summary: SummaryResult,
    ranked_items: List[RankedItem],
    output_dir: Path,
    interests: Optional[InterestsConfig] = None,
    date: Optional[str] = None,
    language: str = "en",
) -> Optional[Path]:
    """
    Convenience function to write HTML report only.

    Note: Static HTML generation is deprecated. Web display is now handled
    by Flask server (dbradar/server.py) which reads from JSON files directly.
    This function returns None.

    Args:
        summary: SummaryResult from summarizer.
        ranked_items: List of ranked items for score visualization.
        output_dir: Directory to write the HTML file.
        interests: Optional interests config for sidebar display.
        date: Optional date string (YYYY-MM-DD), defaults to today.
        language: Output language (en/zh).

    Returns:
        None (static HTML generation deprecated).
    """
    # Static HTML generation deprecated - Flask server handles web display
    return None
