"""Report formatter for multiple output formats."""

import json

from .types import Report, ReportFormat


# Translation dictionary for report labels
TRANSLATIONS = {
    "zh": {
        "investment_analysis_report": "投资分析报告",
        "generated": "生成时间",
        "model": "模型",
        "duration": "耗时",
        "summary": "摘要",
        "investment_rating": "投资评级",
        "rating": "评级",
        "confidence": "置信度",
        "target_price": "目标价",
        "scenario_analysis": "情景分析",
        "bull_case": "乐观情景",
        "base_case": "中性情景",
        "bear_case": "悲观情景",
        "detailed_analysis": "详细分析",
        "investment_thesis": "投资论点",
        "price_target_methodology": "目标价与方法论",
        "technical_picture": "技术面分析",
        "fundamental_analysis": "基本面分析",
        "sector_comparables": "行业与可比公司",
        "key_catalysts": "关键催化剂",
        "risk_factors": "风险因素",
        "recommendation": "投资建议",
        "disclaimer": "免责声明",
        "disclaimer_text": "本报告由AI生成，仅供参考，不构成投资建议。投资有风险，请独立判断。",
        "conviction": "确信度",
        "methodology": "方法论",
        "upside_downside": "上涨/下跌空间",
    },
    "en": {
        "investment_analysis_report": "Investment Analysis Report",
        "generated": "Generated",
        "model": "Model",
        "duration": "Duration",
        "summary": "Summary",
        "investment_rating": "Investment Rating",
        "rating": "Rating",
        "confidence": "Confidence",
        "target_price": "Target Price",
        "scenario_analysis": "Scenario Analysis",
        "bull_case": "Bull Case",
        "base_case": "Base Case",
        "bear_case": "Bear Case",
        "detailed_analysis": "Detailed Analysis",
        "investment_thesis": "Investment Thesis",
        "price_target_methodology": "Price Target & Methodology",
        "technical_picture": "Technical Picture",
        "fundamental_analysis": "Fundamental Analysis",
        "sector_comparables": "Sector & Comparables",
        "key_catalysts": "Key Catalysts",
        "risk_factors": "Risk Factors",
        "recommendation": "Recommendation",
        "disclaimer": "Disclaimer",
        "disclaimer_text": "This report is AI-generated for reference only and does not constitute investment advice. Investing involves risks. Please conduct your own research before making investment decisions.",
        "conviction": "Conviction",
        "methodology": "Methodology",
        "upside_downside": "Upside/Downside",
    },
}


class ReportFormatter:
    """Format reports for multiple output formats.

    Supports Markdown, HTML, and JSON formats.
    """

    @staticmethod
    def format(
        report: Report,
        format_type: ReportFormat = ReportFormat.MARKDOWN,
        lang: str = "zh",
    ) -> str:
        """Format report to specified format.

        Args:
            report: Report instance.
            format_type: Output format.
            lang: Output language ("zh" for Chinese, "en" for English).

        Returns:
            Formatted report string.
        """
        formatters = {
            ReportFormat.MARKDOWN: ReportFormatter._to_markdown,
            ReportFormat.HTML: ReportFormatter._to_html,
            ReportFormat.JSON: ReportFormatter._to_json,
        }
        formatter = formatters.get(format_type, ReportFormatter._to_markdown)
        return formatter(report, lang=lang)

    @staticmethod
    def _to_markdown(report: Report, lang: str = "zh") -> str:
        """Convert report to Markdown format.

        Args:
            report: Report instance.
            lang: Output language ("zh" or "en").

        Returns:
            Markdown string.
        """
        t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
        md = ""

        # Title
        title = report.title or f"{report.stock_name} ({report.stock_code}) {t['investment_analysis_report']}"
        md += f"# {title}\n\n"

        # Metadata
        md += f"**{t['generated']}**: {report.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        md += f"**{t['model']}**: {report.model_name}\n"
        md += f"**{t['duration']}**: {report.analysis_duration:.2f}s\n\n"

        # Summary
        if report.summary:
            md += f"## {t['summary']}\n\n{report.summary}\n\n"

        # Rating
        if report.rating:
            md += f"## {t['investment_rating']}\n\n"
            rating_emoji = {
                "Strong Buy": "🔥",
                "Buy": "👍",
                "Hold": "😐",
                "Caution": "⚠️",
                "Sell": "❌",
            }
            emoji = rating_emoji.get(report.rating, "📊")
            md += f"| {t['rating']} | Value |\n|--------|-------|\n"
            md += f"| {t['rating']} | {emoji} {report.rating} |\n"
            if report.confidence:
                md += f"| {t['confidence']} | {report.confidence} |\n"
            if report.target_price:
                md += f"| {t['target_price']} | ¥{report.target_price:.2f} |\n"
            md += "\n"

        # Bull/Bear/Base Cases
        if report.bull_case or report.bear_case or report.base_case:
            md += f"## {t['scenario_analysis']}\n\n"
            if report.bull_case:
                md += f"### {t['bull_case']}\n\n{report.bull_case}\n\n"
            if report.base_case:
                md += f"### {t['base_case']}\n\n{report.base_case}\n\n"
            if report.bear_case:
                md += f"### {t['bear_case']}\n\n{report.bear_case}\n\n"

        # Sections
        md += f"## {t['detailed_analysis']}\n\n"
        for section in report.sections:
            md += f"### {section.title}\n\n"
            md += f"{section.content}\n\n"

        # Disclaimer
        md += "---\n\n"
        md += f"## {t['disclaimer']}\n\n"
        md += f"{t['disclaimer_text']}\n"

        return md

    @staticmethod
    def _to_html(report: Report, lang: str = "zh") -> str:
        """Convert report to HTML format.

        Args:
            report: Report instance.
            lang: Output language ("zh" or "en").

        Returns:
            HTML string with embedded styles.
        """
        try:
            import markdown

            md_content = ReportFormatter._to_markdown(report, lang=lang)
            html_body = markdown.markdown(
                md_content,
                extensions=["tables", "fenced_code", "toc"],
            )
        except ImportError:
            html_body = f"<div>{report.title}</div>"

        t = TRANSLATIONS.get(lang, TRANSLATIONS["zh"])
        html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title or t['investment_analysis_report']}</title>
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
    def _to_json(report: Report, lang: str = "zh") -> str:
        """Convert report to JSON format.

        Args:
            report: Report instance.
            lang: Output language ("zh" or "en") - not used for JSON but kept for consistency.

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
            "raw_data": report.raw_data,
            "sections": [
                {"title": s.title, "content": s.content, "order": s.order}
                for s in report.sections
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
