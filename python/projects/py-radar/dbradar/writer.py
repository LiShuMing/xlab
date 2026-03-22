"""Write reports to Markdown and JSON files."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dbradar.ranker import RankedItem
from dbradar.summarizer import SummaryResult


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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
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

    def write_report(
        self,
        summary: SummaryResult,
        ranked_items: List[RankedItem],
        fetch_failures: List[Dict[str, str]],
        date: Optional[str] = None,
    ) -> tuple:
        """
        Write both Markdown and JSON reports.

        Args:
            summary: SummaryResult from summarizer.
            ranked_items: List of ranked items for reference.
            fetch_failures: List of fetch failure records.
            date: Optional date string (YYYY-MM-DD), defaults to today.

        Returns:
            Tuple of (markdown_path, json_path).
        """
        report_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        report = Report(
            date=report_date,
            title=self.t["title"].format(date=report_date),
            executive_summary=summary.executive_summary,
            top_updates=summary.top_updates,
            release_notes=summary.release_notes,
            themes=summary.themes,
            action_items=summary.action_items,
            fetch_failures=fetch_failures,
            metadata={
                "total_items_collected": len(ranked_items),
                "top_items_count": len(summary.top_updates),
                "language": self.language,
            },
        )

        md_path = self.write_markdown(report)
        json_path = self.write_json(report)

        return md_path, json_path


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
