"""Report comparator for detecting significant changes.

This module compares today's stock analysis report against yesterday's
to identify changes that exceed defined thresholds.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from core.logger import get_logger

logger = get_logger("diff.comparator")


# Thresholds for triggering detailed analysis
PRICE_CHANGE_THRESHOLD = 2.0  # Percentage
PE_PB_CHANGE_THRESHOLD = 5.0  # Percentage
RATING_CHANGE_TRIGGERS = True  # Any rating or confidence change triggers analysis


@dataclass
class Change:
    """Represents a detected change between two reports.

    Attributes:
        field: Field name that changed (e.g., "price", "rating", "news").
        old_value: Previous value.
        new_value: Current value.
        change_pct: Percentage change for numeric fields.
        triggers_analysis: Whether this change should trigger detailed analysis.
        details: Additional details about the change.
    """

    field: str
    old_value: Any
    new_value: Any
    change_pct: Optional[float] = None
    triggers_analysis: bool = False
    details: dict = field(default_factory=dict)


@dataclass
class IncrementalReport:
    """Incremental report containing detected changes.

    Attributes:
        stock_code: Stock ticker symbol.
        stock_name: Company name.
        is_first_run: True if no yesterday data exists.
        changes: List of detected changes.
        report_data: Full report JSON for reference.
        has_significant_changes: True if any change triggers analysis.
    """

    stock_code: str
    stock_name: str
    is_first_run: bool = False
    changes: list[Change] = field(default_factory=list)
    report_data: dict = field(default_factory=dict)
    has_significant_changes: bool = False

    def add_change(self, change: Change) -> None:
        """Add a change and update significant flag.

        Args:
            change: Change to add.
        """
        self.changes.append(change)
        if change.triggers_analysis:
            self.has_significant_changes = True


def compare_reports(today: dict, yesterday: Optional[dict]) -> IncrementalReport:
    """Compare two Report JSON dicts and return changes.

    Args:
        today: Today's report as JSON dict.
        yesterday: Yesterday's report as JSON dict, or None if first run.

    Returns:
        IncrementalReport with detected changes.
    """
    stock_code = today.get("stock_code", "unknown")
    stock_name = today.get("stock_name", "")

    incremental = IncrementalReport(
        stock_code=stock_code,
        stock_name=stock_name,
        report_data=today,
    )

    # Handle first run case - no yesterday data
    if yesterday is None:
        incremental.is_first_run = True
        logger.info("First run for stock", stock_code=stock_code)
        # Add initial state as "changes" for first run
        _add_initial_changes(incremental, today)
        return incremental

    # Compare each field type
    _check_price_change(incremental, today, yesterday)
    _check_rating_change(incremental, today, yesterday)
    _check_target_price_change(incremental, today, yesterday)
    _check_news_change(incremental, today, yesterday)
    _check_pe_pb_change(incremental, today, yesterday)
    _check_support_resistance_break(incremental, today, yesterday)

    logger.info(
        "Comparison complete",
        stock_code=stock_code,
        changes_count=len(incremental.changes),
        has_significant=incremental.has_significant_changes,
    )

    return incremental


def _add_initial_changes(incremental: IncrementalReport, today: dict) -> None:
    """Add initial state as changes for first run.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
    """
    raw_data = today.get("raw_data", {})
    price_data = raw_data.get("price", {})

    # Add initial price
    if price_data:
        incremental.add_change(Change(
            field="price",
            old_value=None,
            new_value=price_data.get("current_price"),
            triggers_analysis=True,
            details={
                "description": "Initial price tracking",
                "prev_close": price_data.get("prev_close"),
                "change_percent": price_data.get("change_percent"),
            },
        ))

    # Add initial rating
    if today.get("rating"):
        incremental.add_change(Change(
            field="rating",
            old_value=None,
            new_value=today.get("rating"),
            triggers_analysis=True,
            details={
                "confidence": today.get("confidence"),
            },
        ))

    # Mark as significant for first run
    incremental.has_significant_changes = True


def _check_price_change(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check if price changed beyond threshold.

    Uses raw_data.price.current_price and compares to yesterday's
    raw_data.price.prev_close for accurate comparison.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    today_raw = today.get("raw_data", {})
    yesterday_raw = yesterday.get("raw_data", {})

    today_price = today_raw.get("price", {})
    yesterday_price = yesterday_raw.get("price", {})

    # Handle both dict and float/int price formats
    if isinstance(today_price, (int, float)):
        today_current = today_price
    else:
        today_current = today_price.get("current_price")

    if isinstance(yesterday_price, (int, float)):
        yesterday_close = yesterday_price
    else:
        yesterday_close = yesterday_price.get("current_price") or yesterday_price.get("prev_close")

    if today_current is None or yesterday_close is None:
        return

    try:
        change_pct = ((today_current - yesterday_close) / yesterday_close) * 100
        change_pct = round(change_pct, 2)

        if abs(change_pct) > PRICE_CHANGE_THRESHOLD:
            incremental.add_change(Change(
                field="price",
                old_value=yesterday_close,
                new_value=today_current,
                change_pct=change_pct,
                triggers_analysis=True,
                details={
                    "yesterday_close": yesterday_close,
                    "today_close": today_current,
                    "threshold_exceeded": abs(change_pct) > PRICE_CHANGE_THRESHOLD,
                },
            ))
            logger.debug(
                "Price change detected",
                stock_code=incremental.stock_code,
                change_pct=change_pct,
            )
    except (TypeError, ZeroDivisionError) as e:
        logger.warning("Failed to calculate price change", error=str(e))


def _check_rating_change(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check if rating or confidence changed.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    today_rating = today.get("rating", "")
    yesterday_rating = yesterday.get("rating", "")

    today_confidence = today.get("confidence", "")
    yesterday_confidence = yesterday.get("confidence", "")

    changes_detected = []

    # Check rating change
    if today_rating and today_rating != yesterday_rating:
        changes_detected.append(f"rating: {yesterday_rating} -> {today_rating}")

    # Check confidence change
    if today_confidence and today_confidence != yesterday_confidence:
        changes_detected.append(f"confidence: {yesterday_confidence} -> {today_confidence}")

    if changes_detected:
        incremental.add_change(Change(
            field="rating",
            old_value=f"{yesterday_rating} ({yesterday_confidence})",
            new_value=f"{today_rating} ({today_confidence})",
            triggers_analysis=True,
            details={
                "old_rating": yesterday_rating,
                "new_rating": today_rating,
                "old_confidence": yesterday_confidence,
                "new_confidence": today_confidence,
                "changes": changes_detected,
            },
        ))
        logger.debug(
            "Rating change detected",
            stock_code=incremental.stock_code,
            changes=changes_detected,
        )


def _check_target_price_change(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check if target price changed significantly.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    today_target = today.get("target_price")
    yesterday_target = yesterday.get("target_price")

    if today_target is None or yesterday_target is None:
        return

    try:
        today_target = float(today_target)
        yesterday_target = float(yesterday_target)

        if yesterday_target == 0:
            return

        change_pct = ((today_target - yesterday_target) / yesterday_target) * 100
        change_pct = round(change_pct, 2)

        # Target price changes are always significant
        if change_pct != 0:
            incremental.add_change(Change(
                field="target_price",
                old_value=yesterday_target,
                new_value=today_target,
                change_pct=change_pct,
                triggers_analysis=True,
                details={
                    "old_target": yesterday_target,
                    "new_target": today_target,
                },
            ))
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logger.warning("Failed to calculate target price change", error=str(e))


def _check_news_change(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check for new news items (deduplicated by title + hour).

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    today_raw = today.get("raw_data", {})
    yesterday_raw = yesterday.get("raw_data", {})

    today_news = today_raw.get("news", {}).get("news", [])
    yesterday_news = yesterday_raw.get("news", {}).get("news", [])

    # Create deduplication keys from yesterday's news (title + hour)
    yesterday_keys = set()
    for item in yesterday_news:
        title = item.get("title", "")
        published_at = item.get("published_at", "")
        # Extract hour from timestamp (format: "YYYY-MM-DD HH:MM")
        hour = published_at.split(" ")[1][:2] if " " in published_at else ""
        key = f"{title}|{hour}"
        yesterday_keys.add(key)

    # Find new news items
    new_items = []
    for item in today_news:
        title = item.get("title", "")
        published_at = item.get("published_at", "")
        hour = published_at.split(" ")[1][:2] if " " in published_at else ""
        key = f"{title}|{hour}"

        if key not in yesterday_keys:
            new_items.append({
                "title": title,
                "source": item.get("source", ""),
                "published_at": published_at,
                "link": item.get("link", ""),
            })

    if new_items:
        incremental.add_change(Change(
            field="news",
            old_value=len(yesterday_news),
            new_value=len(today_news),
            triggers_analysis=True,
            details={
                "new_count": len(new_items),
                "new_items": new_items[:5],  # Limit to first 5 for email
                "total_today": len(today_news),
            },
        ))
        logger.debug(
            "New news detected",
            stock_code=incremental.stock_code,
            new_count=len(new_items),
        )


def _check_pe_pb_change(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check if PE/PB ratios changed beyond threshold.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    today_raw = today.get("raw_data", {})
    yesterday_raw = yesterday.get("raw_data", {})

    today_financials = today_raw.get("financials", {})
    yesterday_financials = yesterday_raw.get("financials", {})

    # Check PE ratio
    today_pe = today_financials.get("trailing_pe")
    yesterday_pe = yesterday_financials.get("trailing_pe")

    if today_pe is not None and yesterday_pe is not None:
        try:
            today_pe = float(today_pe)
            yesterday_pe = float(yesterday_pe)

            if yesterday_pe != 0:
                change_pct = ((today_pe - yesterday_pe) / yesterday_pe) * 100
                change_pct = round(change_pct, 2)

                if abs(change_pct) > PE_PB_CHANGE_THRESHOLD:
                    incremental.add_change(Change(
                        field="pe_ratio",
                        old_value=round(yesterday_pe, 2),
                        new_value=round(today_pe, 2),
                        change_pct=change_pct,
                        triggers_analysis=True,
                    ))
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    # Check PB ratio
    today_pb = today_financials.get("price_to_book")
    yesterday_pb = yesterday_financials.get("price_to_book")

    if today_pb is not None and yesterday_pb is not None:
        try:
            today_pb = float(today_pb)
            yesterday_pb = float(yesterday_pb)

            if yesterday_pb != 0:
                change_pct = ((today_pb - yesterday_pb) / yesterday_pb) * 100
                change_pct = round(change_pct, 2)

                if abs(change_pct) > PE_PB_CHANGE_THRESHOLD:
                    incremental.add_change(Change(
                        field="pb_ratio",
                        old_value=round(yesterday_pb, 2),
                        new_value=round(today_pb, 2),
                        change_pct=change_pct,
                        triggers_analysis=True,
                    ))
        except (TypeError, ValueError, ZeroDivisionError):
            pass


def _check_support_resistance_break(
    incremental: IncrementalReport,
    today: dict,
    yesterday: dict,
) -> None:
    """Check if price broke support or resistance levels.

    This is determined by analyzing the technical section content
    for mentions of breakouts or breakdowns.

    Args:
        incremental: IncrementalReport to update.
        today: Today's report data.
        yesterday: Yesterday's report data.
    """
    # Get technical analysis section
    technical_section = None
    for section in today.get("sections", []):
        title = section.get("title", "")
        if title in ["Technical Picture", "Technical Analysis", "Technical Analysis", "Technical Picture"]:
            technical_section = section.get("content", "")
            break

    if not technical_section:
        return

    # Look for breakout/breakdown keywords
    breakout_keywords = [
        "breakout", "break out", "broken above",
        "breakdown", "broken below", "break down",
        "resistance", "support",
    ]

    technical_lower = technical_section.lower()

    detected_breaks = []
    for keyword in breakout_keywords:
        if keyword in technical_lower:
            detected_breaks.append(keyword)

    # Only report if there's a clear breakout/breakdown
    if "breakout" in technical_lower or "breakdown" in technical_lower:
        incremental.add_change(Change(
            field="support_resistance",
            old_value="Within range",
            new_value="Break detected",
            triggers_analysis=True,
            details={
                "keywords_found": detected_breaks[:3],
            },
        ))
        logger.debug(
            "Support/resistance break detected",
            stock_code=incremental.stock_code,
            keywords=detected_breaks[:3],
        )