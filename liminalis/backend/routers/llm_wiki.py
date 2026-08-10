"""Same-origin proxy for the bundled llm-wiki web console."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from backend._shared.http import AsyncClient, HTTPError, make_client, make_unix_socket_client
from backend._shared.http import Response as HTTPResponse
from backend.settings import get_settings

router = APIRouter(tags=["llm-wiki"])

_PROXY_PREFIX = "/llm-wiki"
_HOP_BY_HOP_HEADERS = {
    "connection",
    "date",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "server",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_client: AsyncClient | None = None
_client_key: tuple[str, str, float] | None = None


def _rewrite_llm_wiki_html(content: bytes) -> bytes:
    text = content.decode("utf-8")
    text = text.replace('"/api', f'"{_PROXY_PREFIX}/api')
    text = text.replace("'/api", f"'{_PROXY_PREFIX}/api")
    return text.encode("utf-8")


def _rewrite_location(location: str) -> str:
    if location == "/":
        return f"{_PROXY_PREFIX}/"
    if location.startswith("/api"):
        return f"{_PROXY_PREFIX}{location}"
    return location


def _iter_response_headers(upstream: HTTPResponse, *, body_rewritten: bool) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for key, value in upstream.headers.multi_items():
        normalized = key.lower()
        if normalized in _HOP_BY_HOP_HEADERS:
            continue
        if normalized == "content-length":
            continue
        if normalized == "location":
            value = _rewrite_location(value)
        headers.append((key, value))
    return headers


async def _proxy_llm_wiki(request: Request, path: str = "") -> Response:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP_HEADERS and key.lower() != "host"
    }

    try:
        client = await _get_proxy_client()
        upstream = await client.request(
            request.method,
            _upstream_path(path, request.url.query),
            content=await request.body(),
            headers=headers,
        )
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"llm-wiki unavailable: {exc}") from exc

    content = upstream.content
    content_type = upstream.headers.get("content-type", "")
    body_rewritten = "text/html" in content_type
    if body_rewritten:
        content = _rewrite_llm_wiki_html(content)

    response = Response(
        content=content,
        status_code=upstream.status_code,
        media_type=None,
    )
    for key, value in _iter_response_headers(upstream, body_rewritten=body_rewritten):
        response.headers.append(key, value)
    return response


@router.api_route("/llm-wiki", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def proxy_llm_wiki_root(request: Request) -> Response:
    return await _proxy_llm_wiki(request)


@router.api_route(
    "/llm-wiki/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def proxy_llm_wiki_path(request: Request, path: str) -> Response:
    return await _proxy_llm_wiki(request, path)


def _upstream_path(path: str, query: str = "") -> str:
    upstream_path = "/" if not path else f"/{path.lstrip('/')}"
    if query:
        return f"{upstream_path}?{query}"
    return upstream_path


async def _get_proxy_client() -> AsyncClient:
    global _client, _client_key
    settings = get_settings()
    key = (
        "socket" if settings.llm_wiki_socket else "url",
        str(settings.llm_wiki_socket or settings.llm_wiki_url.rstrip("/")),
        settings.llm_wiki_timeout,
    )
    if _client is not None and _client_key == key:
        return _client

    await dispose_proxy_client()

    if settings.llm_wiki_socket:
        _client = make_unix_socket_client(
            socket_path=settings.llm_wiki_socket,
            base_url="http://llm-wiki",
            follow_redirects=False,
            timeout=settings.llm_wiki_timeout,
        )
    else:
        _client = make_client(
            base_url=settings.llm_wiki_url.rstrip("/"),
            follow_redirects=False,
            timeout=settings.llm_wiki_timeout,
        )
    _client_key = key
    return _client


async def dispose_proxy_client() -> None:
    global _client, _client_key
    if _client is not None:
        await _client.aclose()
    _client = None
    _client_key = None
