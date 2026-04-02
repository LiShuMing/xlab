"""Tests for thread aggregation module."""

from my_email.llm.thread_aggregator import (
    create_default_aggregator,
    extract_base_subject,
    normalize_subject,
    ThreadAggregator,
)


class TestNormalizeSubject:
    """Tests for normalize_subject function."""

    def test_basic_subject(self):
        """Return lowercase for basic subject."""
        assert normalize_subject("Hello World") == "hello world"

    def test_remove_re_prefix(self):
        """Remove Re: prefix."""
        assert normalize_subject("Re: Hello World") == "hello world"

    def test_remove_multiple_re_prefixes(self):
        """Remove multiple Re: prefixes."""
        assert normalize_subject("Re: Re: Re: Hello World") == "hello world"

    def test_remove_fw_prefix(self):
        """Remove Fw: prefix."""
        assert normalize_subject("Fw: Hello World") == "hello world"

    def test_remove_fwd_prefix(self):
        """Remove Fwd: prefix."""
        assert normalize_subject("Fwd: Hello World") == "hello world"

    def test_remove_list_prefix(self):
        """Remove [list-name] prefix."""
        assert normalize_subject("[dev-list] Hello World") == "hello world"

    def test_remove_multiple_prefixes(self):
        """Remove multiple types of prefixes."""
        assert normalize_subject("Re: [dev-list] Fwd: Hello World") == "hello world"

    def test_empty_subject(self):
        """Handle empty subject."""
        assert normalize_subject("") == ""

    def test_whitespace_only(self):
        """Handle whitespace-only subject."""
        assert normalize_subject("   ") == ""

    def test_preserve_content_after_prefix(self):
        """Preserve content after removing prefixes."""
        assert normalize_subject("Re: [iceberg-dev] Apache Iceberg v1.5") == "apache iceberg v1.5"


class TestExtractBaseSubject:
    """Tests for extract_base_subject function."""

    def test_extract_base(self):
        """Extract base subject without prefixes."""
        assert extract_base_subject("Re: Project Update") == "project update"

    def test_same_as_normalize(self):
        """extract_base_subject is an alias for normalize_subject."""
        assert extract_base_subject("[list] Re: Test") == normalize_subject("[list] Re: Test")


class TestThreadAggregatorGroupKey:
    """Tests for _get_group_key method."""

    def test_use_thread_id(self):
        """Use thread_id when available."""
        aggregator = ThreadAggregator()
        msg = {"id": "msg1", "thread_id": "thread123", "subject": "Hello"}
        key = aggregator._get_group_key(msg)
        assert key == "thread:thread123"

    def test_fallback_to_subject(self):
        """Fallback to normalized subject when no thread_id."""
        aggregator = ThreadAggregator()
        msg = {"id": "msg1", "thread_id": "", "subject": "Re: Hello World"}
        key = aggregator._get_group_key(msg)
        assert key == "subject:hello world"

    def test_fallback_when_thread_id_disabled(self):
        """Use subject when use_thread_id=False."""
        aggregator = ThreadAggregator(use_thread_id=False)
        msg = {"id": "msg1", "thread_id": "thread123", "subject": "Hello"}
        key = aggregator._get_group_key(msg)
        assert key == "subject:hello"

    def test_single_message_fallback(self):
        """Use message id when both grouping methods disabled."""
        aggregator = ThreadAggregator(use_thread_id=False, use_subject_similarity=False)
        msg = {"id": "msg1", "thread_id": "", "subject": ""}
        key = aggregator._get_group_key(msg)
        assert key == "single:msg1"


class TestThreadAggregatorAggregate:
    """Tests for aggregate method."""

    def test_single_message(self):
        """Aggregate single message."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body",
            },
        ]

        result = aggregator.aggregate(messages)

        assert len(result) == 1
        assert result[0]["message_count"] == 1
        assert result[0]["is_thread"] is False
        assert result[0]["message_ids"] == ["msg1"]

    def test_group_by_thread_id(self):
        """Group messages by thread_id."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
            {
                "id": "msg3",
                "thread_id": "t1",
                "subject": "Re: Re: Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T12:00:00Z",
                "body_text": "Body3",
            },
        ]

        result = aggregator.aggregate(messages)

        assert len(result) == 1
        assert result[0]["message_count"] == 3
        assert result[0]["is_thread"] is True
        assert result[0]["message_ids"] == ["msg1", "msg2", "msg3"]

    def test_group_by_subject(self):
        """Group messages by normalized subject when no thread_id."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "",
                "subject": "Project Update",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "",
                "subject": "Re: Project Update",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        assert len(result) == 1
        assert result[0]["message_count"] == 2
        assert result[0]["is_thread"] is True

    def test_separate_different_subjects(self):
        """Keep different subjects in separate groups."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "",
                "subject": "Project A",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "",
                "subject": "Project B",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        assert len(result) == 2

    def test_separate_different_threads(self):
        """Keep different thread_ids in separate groups."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Topic A",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t2",
                "subject": "Topic B",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        assert len(result) == 2

    def test_empty_list(self):
        """Handle empty message list."""
        aggregator = ThreadAggregator()
        result = aggregator.aggregate([])
        assert result == []

    def test_unique_senders_preserved(self):
        """Extract unique senders preserving order."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
            {
                "id": "msg3",
                "thread_id": "t1",
                "subject": "Re: Re: Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T12:00:00Z",
                "body_text": "Body3",
            },  # Duplicate sender
        ]

        result = aggregator.aggregate(messages)

        assert result[0]["senders"] == ["a@example.com", "b@example.com"]

    def test_date_range(self):
        """Calculate date range from messages."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T14:00:00Z",
                "body_text": "Body2",
            },
            {
                "id": "msg3",
                "thread_id": "t1",
                "subject": "Re: Re: Hello",
                "sender": "c@example.com",
                "received_at": "2026-03-24T12:00:00Z",
                "body_text": "Body3",
            },
        ]

        result = aggregator.aggregate(messages)

        # Should be sorted by received_at
        assert result[0]["date_range"] == ("2026-03-24T10:00:00Z", "2026-03-24T14:00:00Z")


class TestThreadAggregatorMinGroupSize:
    """Tests for min_group_size parameter."""

    def test_min_group_size_keeps_small_groups_separate(self):
        """Keep messages separate when below min_group_size."""
        aggregator = ThreadAggregator(min_group_size=3)
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        # 2 messages < min_group_size=3, so each is separate
        assert len(result) == 2
        assert all(not r["is_thread"] for r in result)

    def test_min_group_size_allows_large_groups(self):
        """Aggregate when group meets min_group_size."""
        aggregator = ThreadAggregator(min_group_size=2)
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        # 2 messages >= min_group_size=2, so aggregated
        assert len(result) == 1
        assert result[0]["is_thread"] is True


class TestThreadAggregatorFormatBody:
    """Tests for body formatting."""

    def test_single_message_format(self):
        """Format single message body."""
        aggregator = ThreadAggregator()
        msg = {
            "id": "msg1",
            "thread_id": "t1",
            "subject": "Hello World",
            "sender": "user@example.com",
            "received_at": "2026-03-24T10:00:00Z",
            "body_text": "This is the message body.",
        }

        result = aggregator.aggregate([msg])

        assert "Subject: Hello World" in result[0]["combined_body"]
        assert "From: user@example.com" in result[0]["combined_body"]
        assert "Date: 2026-03-24T10:00:00Z" in result[0]["combined_body"]
        assert "This is the message body." in result[0]["combined_body"]

    def test_thread_format(self):
        """Format thread with multiple messages."""
        aggregator = ThreadAggregator()
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": "Body1",
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Body2",
            },
        ]

        result = aggregator.aggregate(messages)

        combined = result[0]["combined_body"]
        assert "=== Email Thread: hello ===" in combined
        assert "Total messages in thread: 2" in combined
        assert "--- Message 1/2 ---" in combined
        assert "--- Message 2/2 ---" in combined

    def test_thread_body_truncation(self):
        """Truncate long bodies in threads."""
        aggregator = ThreadAggregator()
        long_body = "x" * 5000  # Very long body
        messages = [
            {
                "id": "msg1",
                "thread_id": "t1",
                "subject": "Hello",
                "sender": "a@example.com",
                "received_at": "2026-03-24T10:00:00Z",
                "body_text": long_body,
            },
            {
                "id": "msg2",
                "thread_id": "t1",
                "subject": "Re: Hello",
                "sender": "b@example.com",
                "received_at": "2026-03-24T11:00:00Z",
                "body_text": "Short",
            },
        ]

        result = aggregator.aggregate(messages)

        assert "[... truncated for thread summarization ...]" in result[0]["combined_body"]


class TestCreateDefaultAggregator:
    """Tests for create_default_aggregator factory function."""

    def test_default_configuration(self):
        """Default aggregator has correct settings."""
        aggregator = create_default_aggregator()

        assert aggregator.use_thread_id is True
        assert aggregator.use_subject_similarity is True
        assert aggregator.min_group_size == 1

    def test_returns_thread_aggregator(self):
        """Factory returns ThreadAggregator instance."""
        aggregator = create_default_aggregator()
        assert isinstance(aggregator, ThreadAggregator)
