"""Lightweight URL normalization shared by ingestion domains."""

from __future__ import annotations

from collections.abc import Collection
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "referrer",
    "source",
}


def normalize_url(url: str, tracking_params: Collection[str] = TRACKING_PARAMS) -> str:
    """Normalize an absolute URL for comparison without loading crawler dependencies."""
    value = url.strip()
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return value

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    try:
        port = parsed.port
    except ValueError:
        return value
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"

    ignored = {item.lower() for item in tracking_params}
    params = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in ignored and not key.lower().startswith("utm_")
    ]
    params.sort(key=lambda item: (item[0].lower(), item[1]))
    query = urlencode(params, doseq=True)

    return urlunsplit((scheme, netloc, parsed.path or "/", query, ""))
