"""Report formatter for multiple output formats."""

import json

from .types import Report, ReportFormat


class ReportFormatter:
    """Format reports for multiple output formats.

    Supports Markdown, HTML, and JSON formats.
    """

    @staticmethod
    def format(report: Report, format_type: ReportFormat = ReportFormat.MARKDOWN) -> str:
        """Format report to specified format.

        Args:
            report: Report instance.
            format_type: Output format.

        Returns:
            Formatted report string.
        """
        formatters = {
            ReportFormat.MARKDOWN: ReportFormatter._to_markdown,
            ReportFormat.HTML: ReportFormatter._to_html,
            ReportFormat.JSON: ReportFormatter._to_json,
        }
        formatter = formatters.get(format_type, ReportFormatter._to_markdown)
        return formatter(report)

    @staticmethod
    def _to_markdown(report: Report) -> str:
        """Convert report to Markdown format.

        Args:
            report: Report instance.

        Returns:
            Markdown string.
        """
        md = ""

        # Title
        title = report.title or f"{report.stock_name} ({report.stock_code}) Investment Analysis"
        md += f"# {title}\n\n"

        # Metadata
        md += f"**Generated**: {report.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        md += f"**Model**: {report.model_name}\n"
        md += f"**Duration**: {report.analysis_duration:.2f}s\n\n"

        # Summary
        if report.summary:
            md += f"## Summary\n\n{report.summary}\n\n"

        # Rating
        if report.rating:
            md += "## Investment Rating\n\n"
            rating_emoji = {
                "Strong Buy": "🔥",
                "Buy": "👍",
                "Hold": "😐",
                "Caution": "⚠️",
                "Sell": "❌",
            }
            emoji = rating_emoji.get(report.rating, "📊")
            md += f"| Metric | Value |\n|--------|-------|\n"
            md += f"| Rating | {emoji} {report.rating} |\n"
            if report.confidence:
                md += f"| Confidence | {report.confidence} |\n"
            if report.target_price:
                md += f"| Target Price | ${report.target_price:.2f} |\n"
            md += "\n"

        # Bull/Bear/Base Cases
        if report.bull_case or report.bear_case or report.base_case:
            md += "## Scenario Analysis\n\n"
            if report.bull_case:
                md += f"### Bull Case\n\n{report.bull_case}\n\n"
            if report.base_case:
                md += f"### Base Case\n\n{report.base_case}\n\n"
            if report.bear_case:
                md += f"### Bear Case\n\n{report.bear_case}\n\n"

        # Sections
        md += "## Detailed Analysis\n\n"
        for section in report.sections:
            md += f"### {section.title}\n\n"
            md += f"{section.content}\n\n"

        # Disclaimer
        md += "---\n\n"
        md += "## Disclaimer\n\n"
        md += "This report is AI-generated for reference only and does not constitute investment advice. "
        md += "Investing involves risks. Please conduct your own research before making investment decisions.\n"

        return md

    @staticmethod
    def _to_html(report: Report) -> str:
        """Convert report to HTML format.

        Args:
            report: Report instance.

        Returns:
            HTML string with embedded styles.
        """
        try:
            import markdown

            md_content = ReportFormatter._to_markdown(report)
            html_body = markdown.markdown(
                md_content,
                extensions=["tables", "fenced_code", "toc"],
            )
        except ImportError:
            html_body = f"<div>{report.title}</div>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title or 'Investment Analysis Report'}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        h3 {{ color: #555; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .rating {{ background: #fff3cd; padding: 15px; border-radius: 8px; }}
        .disclaimer {{ color: #6c757d; font-size: 0.9em; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""
        return html

    @staticmethod
    def _to_json(report: Report) -> str:
        """Convert report to JSON format.

        Args:
            report: Report instance.

        Returns:
            JSON string.
        """
        data = {
            "report_id": report.report_id,
            "stock_code": report.stock_code,
            "stock_name": report.stock_name,
            "title": report.title,
            "summary": report.summary,
            "rating": report.rating,
            "confidence": report.confidence,
            "target_price": report.target_price,
            "bull_case": report.bull_case,
            "bear_case": report.bear_case,
            "base_case": report.base_case,
            "created_at": report.created_at.isoformat(),
            "model_name": report.model_name,
            "analysis_duration": report.analysis_duration,
            "sections": [
                {"title": s.title, "content": s.content, "order": s.order}
                for s in report.sections
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
