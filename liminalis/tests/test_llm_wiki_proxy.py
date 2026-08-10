"""Unit tests for the same-origin llm-wiki proxy helpers."""

from __future__ import annotations

import httpx

from backend.routers.llm_wiki import (
    _iter_response_headers,
    _rewrite_llm_wiki_html,
    _rewrite_location,
    _upstream_path,
)


def test_llm_wiki_html_rewrite_scopes_absolute_api_paths() -> None:
    html = b'<script>fetch("/api/state"); api("/api/chat");</script><img src="/api/asset/file?id=1">'

    rewritten = _rewrite_llm_wiki_html(html).decode("utf-8")

    assert 'fetch("/llm-wiki/api/state")' in rewritten
    assert 'api("/llm-wiki/api/chat")' in rewritten
    assert 'src="/llm-wiki/api/asset/file?id=1"' in rewritten


def test_llm_wiki_proxy_rewrites_redirects_and_preserves_cookie_headers() -> None:
    upstream = httpx.Response(
        303,
        headers=[
            ("Location", "/api/state"),
            ("Set-Cookie", "ctx_token=a; Path=/; HttpOnly"),
            ("Set-Cookie", "ctx_user=b; Path=/"),
            ("Content-Length", "123"),
        ],
    )

    headers = _iter_response_headers(upstream, body_rewritten=False)

    assert _rewrite_location("/") == "/llm-wiki/"
    normalized = [(key.lower(), value) for key, value in headers]
    assert ("location", "/llm-wiki/api/state") in normalized
    assert ("set-cookie", "ctx_token=a; Path=/; HttpOnly") in normalized
    assert ("set-cookie", "ctx_user=b; Path=/") in normalized
    assert not any(key.lower() == "content-length" for key, _ in headers)


def test_llm_wiki_upstream_path_preserves_query() -> None:
    assert _upstream_path("", "") == "/"
    assert _upstream_path("api/csrf", "") == "/api/csrf"
    assert _upstream_path("/api/chat", "q=a%20b") == "/api/chat?q=a%20b"
