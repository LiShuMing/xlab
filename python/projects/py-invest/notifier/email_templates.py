"""HTML email templates for stock analysis reports.

This module provides functions to format stock analysis reports
as HTML emails with professional styling.
"""

from datetime import date, datetime
from typing import Any, Optional

from modules.report_generator.types import Report


def format_stock_report_html(report: Report, lang: str = "zh") -> str:
    """Format a single stock report as HTML email.

    Args:
        report: Report object with analysis data.
        lang: Output language ("zh" or "en").

    Returns:
        HTML string ready for email.
    """
    t = _get_translations(lang)

    # Determine rating style
    rating_style = _get_rating_style(report.rating)

    # Build HTML with inline styles for email client compatibility
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.stock_code} 投资分析</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f0f2f5;">
        <tr>
            <td style="padding: 20px;">
                <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">

    <!-- Header -->
    <tr>
        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 40px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    <td>
                        <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                            {report.stock_name or report.stock_code}
                        </h1>
                        <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">
                            {report.stock_code} · {t['investment_analysis_report']}
                        </p>
                    </td>
                    <td style="text-align: right;">
                        <div style="background-color: rgba(255,255,255,0.2); border-radius: 8px; padding: 12px 20px; display: inline-block;">
                            <span style="color: #ffffff; font-size: 14px;">{t['generated']}</span><br>
                            <span style="color: #ffffff; font-size: 18px; font-weight: 600;">{report.created_at.strftime('%Y-%m-%d')}</span>
                        </div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>

    <!-- Rating Section -->
    {_build_rating_section(report, t, rating_style)}

    <!-- Summary Section -->
    {_build_summary_section(report, t)}

    <!-- Scenario Analysis -->
    {_build_scenario_section(report, t)}

    <!-- Detailed Analysis -->
    {_build_detail_section(report, t)}

    <!-- Footer -->
    <tr>
        <td style="padding: 30px 40px; border-top: 1px solid #e5e7eb;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    <td style="color: #6b7280; font-size: 13px;">
                        <p style="margin: 0 0 8px 0;">
                            <strong>{t['model']}:</strong> {report.model_name} &nbsp;|&nbsp;
                            <strong>{t['duration']}:</strong> {report.analysis_duration:.1f}s
                        </p>
                        <p style="margin: 0; color: #9ca3af; font-size: 12px; line-height: 1.6;">
                            ⚠️ {t['disclaimer_text']}
                        </p>
                    </td>
                </tr>
            </table>
        </td>
    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    return html


def _build_rating_section(report: Report, t: dict, rating_style: dict) -> str:
    """Build rating section HTML."""
    if not report.rating:
        return ""

    emoji = _rating_emoji(report.rating)

    return f"""
    <!-- Rating Card -->
    <tr>
        <td style="padding: 30px 40px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: {rating_style['bg']}; border-radius: 12px; border-left: 4px solid {rating_style['border']};">
                <tr>
                    <td style="padding: 25px 30px;">
                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                            <tr>
                                <td style="width: 50%; vertical-align: top;">
                                    <p style="margin: 0 0 5px 0; color: #6b7280; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">{t['investment_rating']}</p>
                                    <p style="margin: 0; font-size: 36px; font-weight: 700; color: {rating_style['text']};">
                                        {emoji} {report.rating}
                                    </p>
                                </td>
                                <td style="width: 50%; vertical-align: top; text-align: right;">
                                    {_build_rating_metrics(report, t)}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </td>
    </tr>"""


def _build_rating_metrics(report: Report, t: dict) -> str:
    """Build rating metrics display."""
    metrics = []

    if report.target_price:
        metrics.append(f"""
            <div style="margin-bottom: 10px;">
                <p style="margin: 0; color: #6b7280; font-size: 12px;">{t['target_price']}</p>
                <p style="margin: 0; font-size: 24px; font-weight: 600; color: #111827;">${report.target_price:.2f}</p>
            </div>
        """)

    if report.confidence:
        confidence_colors = {
            "high": ("#059669", "#d1fae5"),
            "medium": ("#d97706", "#fef3c7"),
            "low": ("#dc2626", "#fee2e2"),
        }
        color_key = report.confidence.lower() if report.confidence.lower() in confidence_colors else "medium"
        text_color, bg_color = confidence_colors[color_key]

        metrics.append(f"""
            <div style="display: inline-block; background-color: {bg_color}; padding: 6px 12px; border-radius: 20px;">
                <span style="color: {text_color}; font-size: 14px; font-weight: 600;">{t['confidence']}: {report.confidence}</span>
            </div>
        """)

    return "".join(metrics) if metrics else ""


def _build_summary_section(report: Report, t: dict) -> str:
    """Build summary section HTML."""
    if not report.summary:
        return ""

    return f"""
    <!-- Summary -->
    <tr>
        <td style="padding: 0 40px 30px 40px;">
            <h2 style="margin: 0 0 15px 0; font-size: 20px; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                📋 {t['summary']}
            </h2>
            <p style="margin: 0; color: #374151; font-size: 15px; line-height: 1.8;">
                {_format_text(report.summary)}
            </p>
        </td>
    </tr>"""


def _build_scenario_section(report: Report, t: dict) -> str:
    """Build scenario analysis section HTML."""
    if not report.bull_case and not report.base_case and not report.bear_case:
        return ""

    scenarios_html = []

    if report.bull_case:
        scenarios_html.append(f"""
            <td style="width: 33.33%; padding: 0 5px;">
                <div style="background-color: #ecfdf5; border-radius: 8px; padding: 20px; border-top: 3px solid #10b981;">
                    <h3 style="margin: 0 0 10px 0; color: #059669; font-size: 16px;">📈 {t['bull_case']}</h3>
                    <p style="margin: 0; color: #065f46; font-size: 13px; line-height: 1.6;">
                        {_format_text(report.bull_case[:200])}{'...' if len(report.bull_case) > 200 else ''}
                    </p>
                </div>
            </td>
        """)

    if report.base_case:
        scenarios_html.append(f"""
            <td style="width: 33.33%; padding: 0 5px;">
                <div style="background-color: #fffbeb; border-radius: 8px; padding: 20px; border-top: 3px solid #f59e0b;">
                    <h3 style="margin: 0 0 10px 0; color: #d97706; font-size: 16px;">⚖️ {t['base_case']}</h3>
                    <p style="margin: 0; color: #92400e; font-size: 13px; line-height: 1.6;">
                        {_format_text(report.base_case[:200])}{'...' if len(report.base_case) > 200 else ''}
                    </p>
                </div>
            </td>
        """)

    if report.bear_case:
        scenarios_html.append(f"""
            <td style="width: 33.33%; padding: 0 5px;">
                <div style="background-color: #fef2f2; border-radius: 8px; padding: 20px; border-top: 3px solid #ef4444;">
                    <h3 style="margin: 0 0 10px 0; color: #dc2626; font-size: 16px;">📉 {t['bear_case']}</h3>
                    <p style="margin: 0; color: #991b1b; font-size: 13px; line-height: 1.6;">
                        {_format_text(report.bear_case[:200])}{'...' if len(report.bear_case) > 200 else ''}
                    </p>
                </div>
            </td>
        """)

    return f"""
    <!-- Scenario Analysis -->
    <tr>
        <td style="padding: 0 40px 30px 40px;">
            <h2 style="margin: 0 0 15px 0; font-size: 20px; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                📊 {t['scenario_analysis']}
            </h2>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                    {''.join(scenarios_html)}
                </tr>
            </table>
        </td>
    </tr>"""


def _build_detail_section(report: Report, t: dict) -> str:
    """Build detailed analysis section HTML."""
    if not report.sections:
        return ""

    sections_html = []
    for i, section in enumerate(report.sections):
        icon = ["💡", "📉", "⚠️", "🏭", "🎯", "💰"][i % 6]
        sections_html.append(f"""
        <div style="margin-bottom: 20px; padding: 20px; background-color: #f9fafb; border-radius: 8px;">
            <h3 style="margin: 0 0 10px 0; color: #111827; font-size: 16px;">{icon} {section.title}</h3>
            <div style="color: #374151; font-size: 14px; line-height: 1.7;">
                {_format_text(section.content)}
            </div>
        </div>
        """)

    return f"""
    <!-- Detailed Analysis -->
    <tr>
        <td style="padding: 0 40px 30px 40px;">
            <h2 style="margin: 0 0 15px 0; font-size: 20px; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
                📑 {t['detailed_analysis']}
            </h2>
            {''.join(sections_html)}
        </td>
    </tr>"""


def format_daily_summary_html(
    reports: list[Report],
    date_str: str,
    lang: str = "zh",
) -> str:
    """Format a daily summary email with multiple stocks.

    Args:
        reports: List of Report objects.
        date_str: Date string for subject.
        lang: Output language ("zh" or "en").

    Returns:
        HTML string ready for email.
    """
    t = _get_translations(lang)

    # Build stock cards
    stock_cards = []
    for report in reports:
        rating_style = _get_rating_style(report.rating)
        emoji = _rating_emoji(report.rating)

        stock_cards.append(f"""
            <tr>
                <td style="padding: 15px; background-color: #ffffff; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="width: 60%;">
                                <h3 style="margin: 0; color: #111827; font-size: 18px;">{report.stock_name}</h3>
                                <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">{report.stock_code}</p>
                            </td>
                            <td style="width: 20%; text-align: center;">
                                <span style="font-size: 24px; font-weight: 700; color: {rating_style['text']};">{emoji}</span>
                            </td>
                            <td style="width: 20%; text-align: right;">
                                <p style="margin: 0; font-size: 20px; font-weight: 600; color: #111827;">
                                    ${report.target_price:.2f if report.target_price else '-'}
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        """)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f0f2f5;">
        <tr>
            <td style="padding: 20px;">
                <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden;">

    <!-- Header -->
    <tr>
        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 40px;">
            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                📈 {t['daily_report']}
            </h1>
            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.8); font-size: 16px;">
                {date_str}
            </p>
        </td>
    </tr>

    <!-- Stocks List -->
    <tr>
        <td style="padding: 30px 40px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                {''.join(stock_cards)}
            </table>
        </td>
    </tr>

    <!-- Footer -->
    <tr>
        <td style="padding: 20px 40px; border-top: 1px solid #e5e7eb;">
            <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                ⚠️ {t['disclaimer_text']}
            </p>
        </td>
    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _get_translations(lang: str) -> dict[str, str]:
    """Get translation dictionary for the specified language."""
    translations = {
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
            "disclaimer_text": "本报告由AI生成，仅供参考，不构成投资建议。投资有风险，请独立判断。",
            "daily_report": "每日投资分析",
            "summary_overview": "概览",
            "stock": "股票",
        },
        "en": {
            "investment_analysis_report": "Investment Analysis",
            "generated": "Generated",
            "model": "Model",
            "duration": "Duration",
            "summary": "Summary",
            "investment_rating": "Rating",
            "rating": "Rating",
            "confidence": "Confidence",
            "target_price": "Target",
            "scenario_analysis": "Scenario Analysis",
            "bull_case": "Bull Case",
            "base_case": "Base Case",
            "bear_case": "Bear Case",
            "detailed_analysis": "Detailed Analysis",
            "disclaimer_text": "This report is AI-generated for reference only and does not constitute investment advice. Investing involves risks.",
            "daily_report": "Daily Investment Analysis",
            "summary_overview": "Overview",
            "stock": "Stock",
        },
    }
    return translations.get(lang, translations["zh"])


def _get_rating_style(rating: Optional[str]) -> dict:
    """Get color style for rating."""
    if not rating:
        return {"text": "#6b7280", "border": "#6b7280", "bg": "#f3f4f6"}

    rating_lower = rating.lower()
    if "buy" in rating_lower or "strong" in rating_lower:
        return {"text": "#059669", "border": "#10b981", "bg": "#ecfdf5"}
    elif "hold" in rating_lower:
        return {"text": "#d97706", "border": "#f59e0b", "bg": "#fffbeb"}
    elif "sell" in rating_lower or "caution" in rating_lower:
        return {"text": "#dc2626", "border": "#ef4444", "bg": "#fef2f2"}

    return {"text": "#3b82f6", "border": "#3b82f6", "bg": "#eff6ff"}


def _rating_emoji(rating: Optional[str]) -> str:
    """Get emoji for rating."""
    if not rating:
        return "📊"
    rating_map = {
        "strong buy": "🔥",
        "buy": "👍",
        "hold": "😐",
        "caution": "⚠️",
        "sell": "❌",
    }
    return rating_map.get(rating.lower(), "📊")


def _format_text(text: str) -> str:
    """Format text with basic markdown conversion."""
    import re

    if not text:
        return ""

    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # Line breaks
    text = text.replace("\n", "<br>")

    return text