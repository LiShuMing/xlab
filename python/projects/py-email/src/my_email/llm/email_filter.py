"""
Email filtering module.

Provides filters to exclude unwanted emails from summarization:
- StarRocks-related emails (configurable exclusion list)
- Auto-reply messages (Out of Office, Delivery Status, etc.)
"""

from __future__ import annotations

import re
from typing import Any

import structlog

log = structlog.get_logger()


# Keywords that indicate StarRocks-related content
STARROCKS_KEYWORDS: list[str] = [
    "starrocks",
    "star rock",
    "sr-",
    "starrocks-",
]

# Subject prefixes that indicate auto-reply messages
AUTO_REPLY_SUBJECT_PATTERNS: list[str] = [
    r"^auto[-\s]reply",
    r"^automatic\s+reply",
    r"^out\s+of\s+office",
    r"^away\s+from\s+office",
    r"^vacation\s+reply",
    r"^delivery\s+status",
    r"^undeliverable",
    r"^delivery\s+failure",
    r"^returned\s+mail",
    r"^bounce",
    r"^非自动回复",  # Chinese
    r"^自动回复",
    r"^外出",
    r"^休假",
]

# Headers that indicate auto-reply (checked in body for simplicity)
AUTO_REPLY_BODY_PATTERNS: list[str] = [
    r"auto-?replied",
    r"automatic\s+reply",
    r"out\s+of\s+office",
    r"away\s+from\s+office",
    r"vacation\s+auto",
    r"i\s+am\s+(currently\s+)?(out\s+of\s+office|away|on\s+vacation)",
    r"自动回复",
    r"外出",
]

# Sender patterns that indicate automated/noreply addresses
NOREPLY_SENDER_PATTERNS: list[str] = [
    r"noreply@",
    r"no-reply@",
    r"donotreply@",
    r"do-not-reply@",
    r"notifications@",
    r"notification@",
    r"automated@",
    r"auto-",
    r"-noreply",
    r"-no-reply",
]


class EmailFilter:
    """
    Email filter that excludes unwanted messages from summarization.

    Filters:
    - StarRocks-related emails
    - Auto-reply messages
    - Noreply/automated senders (optional)
    """

    def __init__(
        self,
        exclude_starrocks: bool = True,
        exclude_auto_reply: bool = True,
        exclude_noreply: bool = False,  # Keep noreply by default (may contain useful notifications)
        custom_excluded_keywords: list[str] | None = None,
    ) -> None:
        self.exclude_starrocks = exclude_starrocks
        self.exclude_auto_reply = exclude_auto_reply
        self.exclude_noreply = exclude_noreply
        self.custom_excluded_keywords = custom_excluded_keywords or []

    def _contains_starrocks(self, subject: str, sender: str, body: str) -> bool:
        """Check if email is related to StarRocks."""
        text = f"{subject} {sender}".lower()
        for keyword in STARROCKS_KEYWORDS:
            if keyword in text:
                return True
        return False

    def _contains_custom_keyword(self, subject: str, sender: str, body: str) -> bool:
        """Check if email contains custom excluded keywords."""
        text = f"{subject} {sender} {body[:500]}".lower()
        for keyword in self.custom_excluded_keywords:
            if keyword.lower() in text:
                return True
        return False

    def _is_auto_reply_subject(self, subject: str) -> bool:
        """Check if subject indicates auto-reply."""
        subject_lower = subject.lower().strip()
        for pattern in AUTO_REPLY_SUBJECT_PATTERNS:
            if re.search(pattern, subject_lower, re.IGNORECASE):
                return True
        return False

    def _is_auto_reply_body(self, body: str) -> bool:
        """Check if body indicates auto-reply."""
        body_lower = body[:1000].lower()  # Check first 1000 chars
        for pattern in AUTO_REPLY_BODY_PATTERNS:
            if re.search(pattern, body_lower, re.IGNORECASE):
                return True
        return False

    def _is_noreply_sender(self, sender: str) -> bool:
        """Check if sender is a noreply/automated address."""
        sender_lower = sender.lower()
        for pattern in NOREPLY_SENDER_PATTERNS:
            if re.search(pattern, sender_lower):
                return True
        return False

    def should_filter(
        self,
        subject: str,
        sender: str,
        body: str,
        message_id: str = "",
    ) -> tuple[bool, str]:
        """
        Determine if an email should be filtered out.

        Args:
            subject: Email subject line.
            sender: Email sender address.
            body: Email body text.
            message_id: Gmail message ID for logging.

        Returns:
            Tuple of (should_filter: bool, reason: str).
            If should_filter is True, reason contains the filter reason.
        """
        # Check StarRocks
        if self.exclude_starrocks and self._contains_starrocks(subject, sender, body):
            log.debug("email_filter.starrocks", message_id=message_id, subject=subject[:50])
            return True, "starrocks"

        # Check custom keywords
        if self.custom_excluded_keywords and self._contains_custom_keyword(subject, sender, body):
            log.debug("email_filter.custom_keyword", message_id=message_id, subject=subject[:50])
            return True, "custom_keyword"

        # Check auto-reply
        if self.exclude_auto_reply:
            if self._is_auto_reply_subject(subject):
                log.debug("email_filter.auto_reply_subject", message_id=message_id, subject=subject[:50])
                return True, "auto_reply"
            if self._is_auto_reply_body(body):
                log.debug("email_filter.auto_reply_body", message_id=message_id, subject=subject[:50])
                return True, "auto_reply"

        # Check noreply sender
        if self.exclude_noreply and self._is_noreply_sender(sender):
            log.debug("email_filter.noreply", message_id=message_id, sender=sender)
            return True, "noreply"

        return False, ""

    def filter_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """
        Filter a list of messages, returning only those that pass.

        Args:
            messages: List of message dicts with 'subject', 'sender', 'body_text', 'id' keys.

        Returns:
            Tuple of (filtered_messages, filter_stats).
            filter_stats is a dict mapping reason -> count.
        """
        filtered: list[dict[str, Any]] = []
        stats: dict[str, int] = {}

        for msg in messages:
            should_filter, reason = self.should_filter(
                subject=msg.get("subject", ""),
                sender=msg.get("sender", ""),
                body=msg.get("body_text", ""),
                message_id=msg.get("id", ""),
            )

            if should_filter:
                stats[reason] = stats.get(reason, 0) + 1
            else:
                filtered.append(msg)

        return filtered, stats


def create_default_filter() -> EmailFilter:
    """
    Create the default email filter with standard exclusions.

    Returns:
        EmailFilter configured with default settings.
    """
    return EmailFilter(
        exclude_starrocks=True,
        exclude_auto_reply=True,
        exclude_noreply=False,
    )