from __future__ import annotations

from backend._shared.web_feed import detect_content_type, is_feed_content, is_feed_url, parse_feed_content

RSS10_FEED = """<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns="http://purl.org/rss/1.0/">
  <channel rdf:about="https://example.test/">
    <title>RDF Feed</title>
    <link>https://example.test/</link>
  </channel>
  <item rdf:about="https://example.test/a">
    <title>RDF Item</title>
    <link>https://example.test/a</link>
    <description>RDF item body</description>
  </item>
</rdf:RDF>
"""


ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Item</title>
    <link href="https://example.test/atom-item" />
    <updated>2026-01-01T00:00:00Z</updated>
    <summary>Atom item body</summary>
  </entry>
</feed>
"""


def test_feedparser_detects_rss10_rdf_content() -> None:
    parsed = parse_feed_content(RSS10_FEED)

    assert is_feed_content(RSS10_FEED) is True
    assert parsed.version == "rss10"
    assert parsed.entries[0].title == "RDF Item"


def test_feedparser_detects_atom_content() -> None:
    parsed = parse_feed_content(ATOM_FEED)

    assert is_feed_content(ATOM_FEED) is True
    assert parsed.version == "atom10"
    assert parsed.entries[0].link == "https://example.test/atom-item"


def test_feed_detection_rejects_plain_html() -> None:
    html = "<html><head><title>Article</title></head><body><article>Hello</article></body></html>"

    assert is_feed_content(html) is False
    assert detect_content_type("https://example.test/article", html) == "html"


def test_feed_url_detection_keeps_conventional_feed_urls() -> None:
    assert is_feed_url("https://example.test/blog/feed") is True
    assert is_feed_url("https://example.test/index.xml") is True
    assert is_feed_url("https://example.test/blog/post") is False
