"""Tests for email filtering module."""

from my_email.llm.email_filter import (
    create_default_filter,
    EmailFilter,
)


class TestEmailFilterStarRocks:
    """Tests for StarRocks filtering."""

    def test_filter_starrocks_in_subject(self):
        """Filter emails with StarRocks in subject."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="[StarRocks] New Release 3.0",
            sender="dev@example.com",
            body="Some content",
        )
        assert should_filter is True
        assert reason == "starrocks"

    def test_filter_starrocks_in_sender(self):
        """Filter emails with StarRocks in sender."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Release announcement",
            sender="starrocks-dev@googlegroups.com",
            body="Some content",
        )
        assert should_filter is True
        assert reason == "starrocks"

    def test_filter_star_rock_variant(self):
        """Filter emails with 'star rock' variant."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Star Rock performance improvements",
            sender="dev@example.com",
            body="Some content",
        )
        assert should_filter is True

    def test_no_filter_when_starrocks_disabled(self):
        """Don't filter StarRocks when exclude_starrocks=False."""
        filter_ = EmailFilter(exclude_starrocks=False)
        should_filter, reason = filter_.should_filter(
            subject="[StarRocks] Release",
            sender="dev@example.com",
            body="Some content",
        )
        assert should_filter is False


class TestEmailFilterCustomKeywords:
    """Tests for custom keyword filtering."""

    def test_filter_custom_keyword(self):
        """Filter emails matching custom keywords."""
        filter_ = EmailFilter(custom_excluded_keywords=["spam", "promotion"])
        should_filter, reason = filter_.should_filter(
            subject="Special Promotion",
            sender="marketing@example.com",
            body="Buy now!",
        )
        assert should_filter is True
        assert reason == "custom_keyword"

    def test_filter_custom_keyword_case_insensitive(self):
        """Custom keyword matching is case insensitive."""
        filter_ = EmailFilter(custom_excluded_keywords=["UNSUBSCRIBE"])
        should_filter, reason = filter_.should_filter(
            subject="Click here to unsubscribe",
            sender="newsletter@example.com",
            body="Some content",
        )
        assert should_filter is True

    def test_no_filter_without_custom_keywords(self):
        """Don't filter if no custom keywords set."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="spam message",
            sender="dev@example.com",
            body="Some content",
        )
        assert should_filter is False


class TestEmailFilterAutoReply:
    """Tests for auto-reply filtering."""

    def test_filter_auto_reply_prefix(self):
        """Filter emails with Auto-Reply: prefix."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Auto-Reply: Out of Office",
            sender="user@example.com",
            body="I am out of office",
        )
        assert should_filter is True
        assert reason == "auto_reply"

    def test_filter_out_of_office(self):
        """Filter Out of Office emails."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Out of Office",
            sender="user@example.com",
            body="I will be back next week",
        )
        assert should_filter is True

    def test_filter_vacation_reply(self):
        """Filter vacation reply emails."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Vacation Reply",
            sender="user@example.com",
            body="On vacation",
        )
        assert should_filter is True

    def test_filter_delivery_status(self):
        """Filter delivery status notifications."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Delivery Status Notification (Failure)",
            sender="mailer-daemon@example.com",
            body="Message could not be delivered",
        )
        assert should_filter is True

    def test_filter_auto_reply_in_body(self):
        """Filter emails with auto-reply indicators in body."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Re: Meeting",
            sender="user@example.com",
            body="This is an automatic reply. I am currently out of the office.",
        )
        assert should_filter is True
        assert reason == "auto_reply"

    def test_filter_vacation_auto_in_body(self):
        """Filter emails with vacation auto indicators."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Re: Project Update",
            sender="user@example.com",
            body="Vacation auto-response: I will respond when I return.",
        )
        assert should_filter is True

    def test_no_filter_normal_reply(self):
        """Don't filter normal reply emails."""
        filter_ = EmailFilter()
        should_filter, reason = filter_.should_filter(
            subject="Re: Project Update",
            sender="user@example.com",
            body="Thanks for the update. Let me review and get back to you.",
        )
        assert should_filter is False

    def test_no_filter_when_auto_reply_disabled(self):
        """Don't filter auto-reply when exclude_auto_reply=False."""
        filter_ = EmailFilter(exclude_auto_reply=False)
        should_filter, reason = filter_.should_filter(
            subject="Out of Office",
            sender="user@example.com",
            body="I am out",
        )
        assert should_filter is False


class TestEmailFilterNoreply:
    """Tests for noreply sender filtering."""

    def test_filter_noreply_sender(self):
        """Filter noreply@ sender when enabled."""
        filter_ = EmailFilter(exclude_noreply=True)
        should_filter, reason = filter_.should_filter(
            subject="Notification",
            sender="noreply@github.com",
            body="Some notification",
        )
        assert should_filter is True
        assert reason == "noreply"

    def test_filter_no_reply_sender(self):
        """Filter no-reply@ sender."""
        filter_ = EmailFilter(exclude_noreply=True)
        should_filter, reason = filter_.should_filter(
            subject="Notification",
            sender="no-reply@example.com",
            body="Some notification",
        )
        assert should_filter is True

    def test_filter_donotreply_sender(self):
        """Filter donotreply@ sender."""
        filter_ = EmailFilter(exclude_noreply=True)
        should_filter, reason = filter_.should_filter(
            subject="Notification",
            sender="donotreply@example.com",
            body="Some notification",
        )
        assert should_filter is True

    def test_filter_notifications_sender(self):
        """Filter notifications@ sender."""
        filter_ = EmailFilter(exclude_noreply=True)
        should_filter, reason = filter_.should_filter(
            subject="Notification",
            sender="notifications@github.com",
            body="Some notification",
        )
        assert should_filter is True

    def test_no_filter_noreply_by_default(self):
        """Don't filter noreply by default (exclude_noreply=False)."""
        filter_ = EmailFilter()  # Default: exclude_noreply=False
        should_filter, reason = filter_.should_filter(
            subject="Notification",
            sender="noreply@github.com",
            body="Some notification",
        )
        assert should_filter is False


class TestEmailFilterMessages:
    """Tests for filter_messages batch function."""

    def test_filter_messages_batch(self):
        """Filter a batch of messages."""
        filter_ = EmailFilter()
        messages = [
            {
                "id": "msg1",
                "subject": "Normal email",
                "sender": "dev@example.com",
                "body_text": "Content",
            },
            {
                "id": "msg2",
                "subject": "Out of Office",
                "sender": "user@example.com",
                "body_text": "Away",
            },
            {
                "id": "msg3",
                "subject": "[StarRocks] Release",
                "sender": "dev@starrocks.com",
                "body_text": "New version",
            },
            {
                "id": "msg4",
                "subject": "Another normal",
                "sender": "user@example.com",
                "body_text": "Content",
            },
        ]

        filtered, stats = filter_.filter_messages(messages)

        assert len(filtered) == 2  # msg1 and msg4
        assert filtered[0]["id"] == "msg1"
        assert filtered[1]["id"] == "msg4"
        assert stats["auto_reply"] == 1
        assert stats["starrocks"] == 1

    def test_filter_messages_empty_list(self):
        """Handle empty message list."""
        filter_ = EmailFilter()
        filtered, stats = filter_.filter_messages([])

        assert filtered == []
        assert stats == {}

    def test_filter_messages_all_filtered(self):
        """Handle when all messages are filtered."""
        filter_ = EmailFilter()
        messages = [
            {
                "id": "msg1",
                "subject": "Out of Office",
                "sender": "user@example.com",
                "body_text": "Away",
            },
            {
                "id": "msg2",
                "subject": "Auto-Reply",
                "sender": "user2@example.com",
                "body_text": "Vacation",
            },
        ]

        filtered, stats = filter_.filter_messages(messages)

        assert filtered == []
        assert stats["auto_reply"] == 2


class TestCreateDefaultFilter:
    """Tests for create_default_filter factory function."""

    def test_default_filter_configuration(self):
        """Default filter has correct settings."""
        filter_ = create_default_filter()

        assert filter_.exclude_starrocks is True
        assert filter_.exclude_auto_reply is True
        assert filter_.exclude_noreply is False
        assert filter_.custom_excluded_keywords == []

    def test_default_filter_is_email_filter(self):
        """Factory returns EmailFilter instance."""
        filter_ = create_default_filter()
        assert isinstance(filter_, EmailFilter)
