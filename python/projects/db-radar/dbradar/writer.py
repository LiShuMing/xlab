"""Write reports to Markdown and JSON files."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dbradar.ranker import RankedItem
from dbradar.summarizer import SummaryResult


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

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date for display."""
        if not date_str or date_str == "unknown":
            return "Date not available"
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
            f"# Daily DB Radar - {report.date}",
            "",
            "## Executive Summary",
            "",
        ]

        for bullet in report.executive_summary:
            lines.append(f"- {bullet}")
        lines.append("")

        if report.top_updates:
            lines.append("## Top Updates")
            lines.append("")
            for update in report.top_updates:
                lines.append(f"### [{update['product']}] {update['title']}")
                lines.append("")
                lines.append("**What changed:**")
                for change in update.get("what_changed", []):
                    lines.append(f"- {change}")
                lines.append("")
                lines.append("**Why it matters:**")
                for why in update.get("why_it_matters", []):
                    lines.append(f"- {why}")
                lines.append("")
                lines.append("**Source(s):**")
                for url in update.get("sources", []):
                    lines.append(f"- {url}")
                lines.append("")
                if update.get("evidence"):
                    lines.append("**Evidence:**")
                    for evidence in update["evidence"]:
                        lines.append(f"> {evidence}")
                    lines.append("")

        if report.release_notes:
            lines.append("## Release Notes Tracker")
            lines.append("")
            lines.append("| Product | Version | Date | Highlights |")
            lines.append("|---------|---------|------|------------|")
            for rn in report.release_notes:
                highlights = "; ".join(rn.get("highlights", [])[:3])
                lines.append(
                    f"| {rn['product']} | {rn.get('version', '-')} | "
                    f"{self._format_date(rn.get('date'))} | {highlights} |"
                )
            lines.append("")

        if report.themes:
            lines.append("## Themes & Trends")
            lines.append("")
            for theme in report.themes:
                lines.append(f"- {theme}")
            lines.append("")

        if report.action_items:
            lines.append("## Action Items for Me")
            lines.append("")
            for item in report.action_items:
                lines.append(f"- {item}")
            lines.append("")

        if report.fetch_failures:
            lines.append("## Fetch Failures")
            lines.append("")
            lines.append("| URL | Reason |")
            lines.append("|-----|--------|")
            for failure in report.fetch_failures:
                lines.append(f"| {failure.get('url', '-')} | {failure.get('reason', '-')} |")
            lines.append("")

        lines.append(f"\n*Report generated at {datetime.now(timezone.utc).isoformat()}*")

        path.write_text("\n".join(lines))
        return path

    def write_json(self, report: Report, filename: Optional[str] = None) -> Path:
        """Write report as JSON."""
        if not filename:
            filename = f"{report.date}.json"

        path = self.output_dir / filename
        path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
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
            title=f"Daily DB Radar - {report_date}",
            executive_summary=summary.executive_summary,
            top_updates=summary.top_updates,
            release_notes=summary.release_notes,
            themes=summary.themes,
            action_items=summary.action_items,
            fetch_failures=fetch_failures,
            metadata={
                "total_items_collected": len(ranked_items),
                "top_items_count": len(summary.top_updates),
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
) -> tuple:
    """Convenience function to write reports."""
    writer = Writer(output_dir)
    return writer.write_report(summary, ranked_items, fetch_failures, date)
