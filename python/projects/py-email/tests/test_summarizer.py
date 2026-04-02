"""
Tests for llm/summarizer.py.
Uses pytest-mock to stub the OpenAI client — no real LLM calls.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from my_email.llm.summarizer import (
    summarize_message,
    EmailSummary,
    _strip_fences,
    LLMOutputValidationError,
)


# ── unit: _strip_fences ───────────────────────────────────────────────────────


def test_strip_fences_no_fences():
    raw = '{"title": "test"}'
    assert _strip_fences(raw) == '{"title": "test"}'


def test_strip_fences_json_fence():
    raw = '```json\n{"title": "test"}\n```'
    assert _strip_fences(raw) == '{"title": "test"}'


def test_strip_fences_plain_fence():
    raw = '```\n{"title": "test"}\n```'
    assert _strip_fences(raw) == '{"title": "test"}'


# ── integration: summarize_message with mocked client ────────────────────────

_VALID_RESPONSE = {
    "title": "Apache Iceberg v1.5 Release",
    "sender_org": "Apache Iceberg",
    "topics": ["iceberg", "table-format", "schema-evolution", "v1.5"],
    "summary": "Iceberg 1.5 ships with improved deletion vectors and faster plan times.",
    "key_points": [
        "Deletion vectors reduce small file overhead",
        "Planning is 30% faster on large tables",
    ],
    "relevance": "high",
}


def _mock_openai_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@patch("my_email.llm.summarizer.OpenAI")
def test_summarize_message_valid(mock_openai_cls):
    client = MagicMock()
    mock_openai_cls.return_value = client
    client.chat.completions.create.return_value = _mock_openai_response(json.dumps(_VALID_RESPONSE))

    result = summarize_message(
        subject="[ANNOUNCE] Apache Iceberg 1.5.0",
        sender="dev@iceberg.apache.org",
        date="2026-03-19T08:00:00Z",
        body="Iceberg 1.5 is released with deletion vectors...",
    )

    assert isinstance(result, EmailSummary)
    assert result.title == "Apache Iceberg v1.5 Release"
    assert result.relevance == "high"
    assert "iceberg" in result.topics


@patch("my_email.llm.summarizer.OpenAI")
def test_summarize_message_with_fences(mock_openai_cls):
    client = MagicMock()
    mock_openai_cls.return_value = client
    client.chat.completions.create.return_value = _mock_openai_response(
        f"```json\n{json.dumps(_VALID_RESPONSE)}\n```"
    )

    result = summarize_message(
        subject="Test", sender="test@example.com", date="2026-03-19", body="body"
    )
    assert result.sender_org == "Apache Iceberg"


@patch("my_email.llm.summarizer.OpenAI")
def test_summarize_message_invalid_json(mock_openai_cls):
    client = MagicMock()
    mock_openai_cls.return_value = client
    client.chat.completions.create.return_value = _mock_openai_response("not json at all")

    with pytest.raises(LLMOutputValidationError):
        summarize_message(subject="Test", sender="x@y.com", date="2026-03-19", body="body")
