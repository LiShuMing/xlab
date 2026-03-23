"""
Email thread aggregation module.

Groups emails by thread_id or similar subject for consolidated summarization.
This helps combine multiple replies to the same email into a single summary.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import structlog

log = structlog.get_logger()


def normalize_subject(subject: str) -> str:
    """
    Normalize email subject for comparison.

    Removes common prefixes like Re:, Fwd:, [list-name], etc.

    Args:
        subject: Raw email subject.

    Returns:
        Normalized subject string.
    """
    if not subject:
        return ""

    # Remove common prefixes iteratively
    normalized = subject.strip()

    while True:
        # Remove Re:, RE:, Fwd:, FW:, Fw: prefixes
        new_normalized = re.sub(
            r'^(re|fw|fwd)\s*:\s*',
            '',
            normalized,
            flags=re.IGNORECASE
        )
        # Remove [list-name] style prefixes
        new_normalized = re.sub(
            r'^\[[^\]]+\]\s*',
            '',
            new_normalized
        )

        if new_normalized == normalized:
            break
        normalized = new_normalized.strip()

    return normalized.lower()


def extract_base_subject(subject: str) -> str:
    """
    Extract the base subject without reply prefixes.

    Args:
        subject: Raw email subject.

    Returns:
        Base subject for thread grouping.
    """
    return normalize_subject(subject)


class ThreadAggregator:
    """
    Aggregates emails by thread_id or similar subject.

    Groups related emails (replies, forwards) together for
    consolidated summarization.
    """

    def __init__(
        self,
        use_thread_id: bool = True,
        use_subject_similarity: bool = True,
        min_group_size: int = 1,  # Minimum emails to form a group
    ) -> None:
        self.use_thread_id = use_thread_id
        self.use_subject_similarity = use_subject_similarity
        self.min_group_size = min_group_size

    def _get_group_key(self, message: dict[str, Any]) -> str:
        """
        Determine the grouping key for a message.

        Priority:
        1. thread_id (if use_thread_id and non-empty)
        2. normalized subject (if use_subject_similarity)

        Args:
            message: Message dict with 'thread_id' and 'subject' keys.

        Returns:
            Group key string.
        """
        thread_id = message.get("thread_id", "")
        subject = message.get("subject", "")

        # Use thread_id if available
        if self.use_thread_id and thread_id:
            return f"thread:{thread_id}"

        # Fall back to normalized subject
        if self.use_subject_similarity:
            base_subject = extract_base_subject(subject)
            return f"subject:{base_subject}"

        # No grouping - each message is its own group
        return f"single:{message.get('id', '')}"

    def aggregate(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Aggregate messages by thread or subject.

        Returns a list of aggregated message groups, each containing:
        - messages: list of original message dicts
        - thread_id: common thread_id (or first message's)
        - subject: the base subject
        - combined_body: concatenated bodies with sender info
        - senders: list of unique senders
        - date_range: (earliest, latest) received_at

        Args:
            messages: List of message dicts.

        Returns:
            List of aggregated group dicts.
        """
        # Group messages by key
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for msg in messages:
            key = self._get_group_key(msg)
            groups[key].append(msg)

        # Build aggregated results
        aggregated: list[dict[str, Any]] = []

        for group_key, group_messages in groups.items():
            if len(group_messages) < self.min_group_size:
                # Keep each message separate
                for msg in group_messages:
                    aggregated.append(self._build_single_message(msg))
            else:
                # Aggregate the group
                aggregated.append(self._build_aggregated_group(group_messages))

        log.info(
            "thread_aggregator.aggregated",
            original_count=len(messages),
            group_count=len(aggregated),
        )

        return aggregated

    def _build_single_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Build an aggregated result for a single message."""
        return {
            "messages": [message],
            "message_ids": [message.get("id", "")],
            "thread_id": message.get("thread_id", ""),
            "subject": message.get("subject", ""),
            "base_subject": extract_base_subject(message.get("subject", "")),
            "combined_body": self._format_single_body(message),
            "senders": [message.get("sender", "")],
            "date_range": (message.get("received_at", ""), message.get("received_at", "")),
            "is_thread": False,
            "message_count": 1,
        }

    def _build_aggregated_group(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build an aggregated result for a group of related messages."""
        # Sort by received_at
        sorted_messages = sorted(
            messages,
            key=lambda m: m.get("received_at", "")
        )

        # Extract info
        first_msg = sorted_messages[0]
        last_msg = sorted_messages[-1]

        senders = list(dict.fromkeys(m.get("sender", "") for m in sorted_messages))  # Unique, preserve order
        message_ids = [m.get("id", "") for m in sorted_messages]

        # Build combined body
        combined_body = self._format_thread_body(sorted_messages)

        return {
            "messages": sorted_messages,
            "message_ids": message_ids,
            "thread_id": first_msg.get("thread_id", ""),
            "subject": first_msg.get("subject", ""),  # Use first subject
            "base_subject": extract_base_subject(first_msg.get("subject", "")),
            "combined_body": combined_body,
            "senders": senders,
            "date_range": (first_msg.get("received_at", ""), last_msg.get("received_at", "")),
            "is_thread": len(sorted_messages) > 1,
            "message_count": len(sorted_messages),
        }

    def _format_single_body(self, message: dict[str, Any]) -> str:
        """Format body for a single message."""
        subject = message.get("subject", "")
        sender = message.get("sender", "")
        date = message.get("received_at", "")
        body = message.get("body_text", "")

        return f"Subject: {subject}\nFrom: {sender}\nDate: {date}\n\n{body}"

    def _format_thread_body(self, messages: list[dict[str, Any]]) -> str:
        """
        Format combined body for a thread of messages.

        Creates a structured format that helps LLM understand the thread.
        """
        parts: list[str] = []

        # Header with thread summary
        first_msg = messages[0]
        base_subject = extract_base_subject(first_msg.get("subject", ""))
        parts.append(f"=== Email Thread: {base_subject} ===")
        parts.append(f"Total messages in thread: {len(messages)}")
        parts.append("")

        # Each message
        for i, msg in enumerate(messages, 1):
            subject = msg.get("subject", "")
            sender = msg.get("sender", "")
            date = msg.get("received_at", "")
            body = msg.get("body_text", "")

            # Truncate very long bodies in threads
            max_body_len = 3000 if len(messages) > 1 else 8000
            if len(body) > max_body_len:
                body = body[:max_body_len] + "\n\n[... truncated for thread summarization ...]"

            parts.append(f"--- Message {i}/{len(messages)} ---")
            parts.append(f"Subject: {subject}")
            parts.append(f"From: {sender}")
            parts.append(f"Date: {date}")
            parts.append("")
            parts.append(body)
            parts.append("")

        return "\n".join(parts)


def create_default_aggregator() -> ThreadAggregator:
    """
    Create the default thread aggregator.

    Returns:
        ThreadAggregator configured with default settings.
    """
    return ThreadAggregator(
        use_thread_id=True,
        use_subject_similarity=True,
        min_group_size=1,
    )