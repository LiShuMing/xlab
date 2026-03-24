"""Email formatter for incremental reports.

This module formats IncrementalReport objects into readable email content
with Chinese language support.
"""

from datetime import datetime
from typing import Optional

from core.logger import get_logger
from .comparator import Change, IncrementalReport

logger = get_logger("diff.formatter")


# Chinese labels for change fields
FIELD_LABELS = {
    "price": "Price Change",
    "rating": "Analyst Recommendation",
    "target_price": "Target Price",
    "news": "New News",
    "pe_ratio": "PE Ratio",
    "pb_ratio": "PB Ratio",
    "support_resistance": "Support/Resistance Break",
}

# Rating emojis
RATING_EMOJIS = {
    "Strong Buy": "Strong Buy",
    "Buy": "Buy",
    "Hold": "Hold",
    "Caution": "Caution",
    "Sell": "Sell",
}

# Confidence emojis
CONFIDENCE_EMOJIS = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def format_incremental_email(
    reports: list[IncrementalReport],
    date_str: str,
    failed_stocks: Optional[list[dict]] = None,
) -> str:
    """Format multiple incremental reports into a single email.

    Args:
        reports: List of IncrementalReport objects.
        date_str: Date string for the email header (YYYY-MM-DD).
        failed_stocks: List of failed stock info with stock_code and error.

    Returns:
        Formatted email content as string.
    """
    lines = []

    # Header
    lines.append(f"Daily Portfolio Report - {date_str}")
    lines.append("")
    lines.append("=" * 50)
    lines.append("")

    # Count reports with changes
    reports_with_changes = [r for r in reports if r.changes]
    reports_without_changes = [r for r in reports if not r.changes]

    if reports_with_changes:
        for report in reports_with_changes:
            lines.append(format_single_stock(report))
            lines.append("")

    # Show stocks without changes (brief mention)
    if reports_without_changes and not reports_with_changes:
        lines.append("### No Significant Changes")
        lines.append("")
        for report in reports_without_changes:
            lines.append(f"- {report.stock_name} ({report.stock_code}): No significant changes")
        lines.append("")

    # Failed stocks section
    if failed_stocks:
        lines.append("=" * 50)
        lines.append("")
        lines.append("### Some Analysis Failed")
        lines.append("")
        success_names = [r.stock_name or r.stock_code for r in reports]
        if success_names:
            lines.append(f"Successful: {', '.join(success_names)}")
        lines.append("Failed stocks:")
        for failed in failed_stocks:
            stock_code = failed.get("stock_code", "unknown")
            error = failed.get("error", "Unknown error")
            lines.append(f"- {stock_code}: {error}")
        lines.append("")

    # Footer
    lines.append("=" * 50)
    lines.append("")
    lines.append("Tip: Run `python cli.py analyze <stock_code>` for detailed analysis")
    lines.append("")

    return "\n".join(lines)


def format_single_stock(report: IncrementalReport) -> str:
    """Format a single stock's changes for email.

    Args:
        report: IncrementalReport for a single stock.

    Returns:
        Formatted string for the stock.
    """
    lines = []

    # Stock header
    lines.append(f"## {report.stock_name} ({report.stock_code})")

    if report.is_first_run:
        lines.append("")
        lines.append("*First time tracking this stock*")

    lines.append("")

    # Format each change
    for change in report.changes:
        lines.append(format_change(change))
        lines.append("")

    return "\n".join(lines)


def format_change(change: Change) -> str:
    """Format a single change for email.

    Args:
        change: Change object to format.

    Returns:
        Formatted string for the change.
    """
    field_label = FIELD_LABELS.get(change.field, change.field)
    lines = []

    lines.append(f"### {field_label}")

    # Price change
    if change.field == "price":
        return _format_price_change(change)

    # Rating change
    elif change.field == "rating":
        return _format_rating_change(change)

    # Target price change
    elif change.field == "target_price":
        return _format_target_price_change(change)

    # News change
    elif change.field == "news":
        return _format_news_change(change)

    # PE/PB change
    elif change.field in ("pe_ratio", "pb_ratio"):
        return _format_valuation_change(change)

    # Support/resistance break
    elif change.field == "support_resistance":
        return _format_support_resistance_change(change)

    # Default formatting
    else:
        old_str = str(change.old_value) if change.old_value is not None else "N/A"
        new_str = str(change.new_value) if change.new_value is not None else "N/A"
        lines.append(f"- Previous: {old_str}")
        lines.append(f"- Current: {new_str}")
        if change.change_pct is not None:
            lines.append(f"- Change: {change.change_pct:+.2f}%")

    return "\n".join(lines)


def _format_price_change(change: Change) -> str:
    """Format price change for email.

    Args:
        change: Change object with price data.

    Returns:
        Formatted price change string.
    """
    lines = []

    details = change.details
    yesterday_close = details.get("yesterday_close")
    today_close = details.get("today_close")

    if change.old_value is not None:
        lines.append(f"- Yesterday Close: {change.old_value:.2f}")
    if change.new_value is not None:
        lines.append(f"- Today Close: {change.new_value:.2f}")

    if change.change_pct is not None:
        direction = "Up" if change.change_pct > 0 else "Down"
        lines.append(f"- Change: {direction} {abs(change.change_pct):.2f}%")

    # Show if threshold exceeded
    if details.get("threshold_exceeded"):
        lines.append(f"- Threshold: >{abs(change.change_pct):.1f}% (>2%)")

    return "\n".join(lines)


def _format_rating_change(change: Change) -> str:
    """Format rating change for email.

    Args:
        change: Change object with rating data.

    Returns:
        Formatted rating change string.
    """
    lines = []
    details = change.details

    old_rating = details.get("old_rating", "N/A")
    new_rating = details.get("new_rating", "N/A")
    old_confidence = details.get("old_confidence", "")
    new_confidence = details.get("new_confidence", "")

    lines.append(f"- Yesterday: {old_rating}" + (f" ({old_confidence})" if old_confidence else ""))
    lines.append(f"- Today: {new_rating}" + (f" ({new_confidence})" if new_confidence else ""))

    # Add recommendation section if available
    if change.triggers_analysis:
        lines.append("")
        lines.append("Analyst view has changed. See detailed analysis.")

    return "\n".join(lines)


def _format_target_price_change(change: Change) -> str:
    """Format target price change for email.

    Args:
        change: Change object with target price data.

    Returns:
        Formatted target price change string.
    """
    lines = []

    if change.old_value is not None:
        lines.append(f"- Previous Target: {change.old_value:.2f}")
    if change.new_value is not None:
        lines.append(f"- New Target: {change.new_value:.2f}")

    if change.change_pct is not None:
        direction = "Up" if change.change_pct > 0 else "Down"
        lines.append(f"- Change: {direction} {abs(change.change_pct):.2f}%")

    return "\n".join(lines)


def _format_news_change(change: Change) -> str:
    """Format news change for email.

    Args:
        change: Change object with news data.

    Returns:
        Formatted news change string.
    """
    lines = []
    details = change.details

    new_items = details.get("new_items", [])
    new_count = details.get("new_count", 0)

    lines.append(f"- New articles: {new_count}")

    if new_items:
        lines.append("")
        lines.append("Recent news:")
        for i, item in enumerate(new_items[:5], 1):
            title = item.get("title", "No title")
            source = item.get("source", "")
            published = item.get("published_at", "")
            lines.append(f"  {i}. {title}")
            if source:
                lines.append(f"     Source: {source}")
            if published:
                lines.append(f"     Time: {published}")

    return "\n".join(lines)


def _format_valuation_change(change: Change) -> str:
    """Format valuation (PE/PB) change for email.

    Args:
        change: Change object with valuation data.

    Returns:
        Formatted valuation change string.
    """
    lines = []

    metric = "PE Ratio" if change.field == "pe_ratio" else "PB Ratio"

    lines.append(f"- Yesterday: {change.old_value:.2f}")
    lines.append(f"- Today: {change.new_value:.2f}")

    if change.change_pct is not None:
        direction = "Up" if change.change_pct > 0 else "Down"
        lines.append(f"- Change: {direction} {abs(change.change_pct):.2f}%")
        lines.append(f"- Threshold: >{abs(change.change_pct):.1f}% (>5%)")

    return "\n".join(lines)


def _format_support_resistance_change(change: Change) -> str:
    """Format support/resistance break for email.

    Args:
        change: Change object with break data.

    Returns:
        Formatted support/resistance break string.
    """
    lines = []

    details = change.details
    keywords = details.get("keywords_found", [])

    lines.append("- Status: Price broke key level detected")
    if keywords:
        lines.append(f"- Key indicators: {', '.join(keywords[:3])}")

    return "\n".join(lines)


def format_email_subject(
    reports: list[IncrementalReport],
    date_str: str,
) -> str:
    """Generate email subject line.

    Args:
        reports: List of IncrementalReport objects.
        date_str: Date string.

    Returns:
        Email subject line.
    """
    total_stocks = len(reports)
    significant_count = sum(1 for r in reports if r.has_significant_changes)
    first_run_count = sum(1 for r in reports if r.is_first_run)

    if first_run_count > 0:
        return f"Portfolio Report ({date_str}) - {first_run_count} new stock(s) added"
    elif significant_count == 0:
        return f"Portfolio Report ({date_str}) - No significant changes"
    else:
        return f"Portfolio Report ({date_str}) - {significant_count}/{total_stocks} stock(s) with changes"