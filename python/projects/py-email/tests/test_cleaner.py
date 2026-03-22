"""
Tests for parser/cleaner.py.
These are pure unit tests — no external I/O.
"""

import pytest
from my_email.parser.cleaner import clean_email_body, MAX_CHARS


def test_plain_text_passthrough():
    body = "Hello world\nThis is a newsletter."
    result = clean_email_body(body, mime_hint="text/plain")
    assert "Hello world" in result
    assert "newsletter" in result


def test_html_stripping():
    html = "<html><body><h1>Apache Iceberg</h1><p>New release 1.5.</p></body></html>"
    result = clean_email_body(html, mime_hint="text/html")
    assert "Apache Iceberg" in result
    assert "New release" in result
    assert "<html>" not in result
    assert "<p>" not in result


def test_noise_tags_removed():
    html = """<html><head><style>body{color:red}</style></head>
    <body><script>alert(1)</script><p>Real content here.</p></body></html>"""
    result = clean_email_body(html, mime_hint="text/html")
    assert "Real content here" in result
    assert "alert" not in result
    assert "color:red" not in result


def test_whitespace_normalization():
    body = "Line one\n\n\n\n\nLine two"
    result = clean_email_body(body, mime_hint="text/plain")
    # Should not have 3+ consecutive newlines
    assert "\n\n\n" not in result


def test_truncation():
    long_body = "x " * 10_000
    result = clean_email_body(long_body, mime_hint="text/plain")
    assert len(result) <= MAX_CHARS + 50  # small buffer for the truncation marker
    assert "[... truncated]" in result


def test_empty_body():
    assert clean_email_body("") == ""
    assert clean_email_body("", mime_hint="text/html") == ""


def test_html_detection_by_content():
    # No mime_hint, but body starts with <html
    html = "<html><body><p>Detected by content.</p></body></html>"
    result = clean_email_body(html)
    assert "Detected by content" in result
    assert "<p>" not in result
