"""GitHub Releases API adapter."""

import re
import structlog
import httpx
from typing import Any

from pia.adapters.base import BaseAdapter
from pia.models.product import Product, ProductSource
from pia.models.release import Release
from pia.utils.dates import now_utc, parse_date
from pia.utils.hashing import hash_content
from pia.utils.versioning import normalize_version

log = structlog.get_logger()

def _make_headers() -> dict:
    """Build GitHub API headers, adding token auth if configured."""
    from pia.config.settings import get_settings
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "pia/1.0 (product intelligence agent)",
    }
    token = get_settings().github_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_api_url(source_url: str) -> str:
    """Convert a GitHub releases API URL to the correct form.

    Handles both:
    - https://api.github.com/repos/owner/repo/releases
    - https://github.com/owner/repo/releases  (converted to API form)

    Args:
        source_url: Source URL from product config.

    Returns:
        GitHub API URL for releases endpoint.
    """
    # Already an API URL
    if "api.github.com" in source_url:
        return source_url.rstrip("/")

    # Convert HTML URL to API URL
    match = re.match(r"https?://github\.com/([^/]+/[^/]+)", source_url)
    if match:
        return f"https://api.github.com/repos/{match.group(1)}/releases"

    return source_url


def _slugify(text: str) -> str:
    """Convert a version tag to a safe ID component.

    Args:
        text: Text to slugify.

    Returns:
        Lowercase alphanumeric string with hyphens.
    """
    return re.sub(r"[^a-zA-Z0-9.\-]", "-", text).strip("-").lower()


class GitHubReleasesAdapter(BaseAdapter):
    """Fetches product releases from the GitHub Releases API."""

    async def fetch_releases(self, product: Product, source: ProductSource) -> list[Release]:
        """Fetch up to 30 releases from the GitHub Releases API.

        Args:
            product: Product configuration.
            source: Source config with GitHub URL.

        Returns:
            List of Release objects.
        """
        api_url = _extract_api_url(source.url)
        params = {"per_page": 30, "page": 1}

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0
        ) as client:
            resp = await client.get(api_url, headers=_make_headers(), params=params)
            resp.raise_for_status()
            items: list[dict[str, Any]] = resp.json()

        releases: list[Release] = []
        for item in items:
            tag_name: str = item.get("tag_name", "")
            version = normalize_version(tag_name)
            body: str = item.get("body") or ""
            html_url: str = item.get("html_url", "")
            name: str = item.get("name") or tag_name

            release_id = f"{product.id}-{_slugify(tag_name)}"

            releases.append(
                Release(
                    id=release_id,
                    product_id=product.id,
                    version=version,
                    title=name,
                    published_at=parse_date(item.get("published_at")),
                    source_url=html_url,
                    source_type="github_releases",
                    source_hash=hash_content(body),
                    discovered_at=now_utc(),
                )
            )

        log.info(
            "github releases fetched",
            product=product.id,
            count=len(releases),
        )
        return releases

    async def fetch_release_content(self, release: Release) -> str:
        """Fetch the release body markdown from the GitHub API.

        For GitHub releases, the content is already available from the
        fetch_releases step. This method re-fetches via the API for a
        single release by constructing the release URL.

        Args:
            release: Release whose content to fetch.

        Returns:
            Release body markdown string.
        """
        # Derive the API URL from the HTML URL
        # html_url: https://github.com/owner/repo/releases/tag/vX.Y.Z
        # api_url:  https://api.github.com/repos/owner/repo/releases/tags/vX.Y.Z
        html_url = release.source_url
        match = re.match(
            r"https?://github\.com/([^/]+/[^/]+)/releases/tag/(.+)", html_url
        )
        if match:
            repo = match.group(1)
            tag = match.group(2)
            api_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                resp = await client.get(api_url, headers=_make_headers())
                resp.raise_for_status()
                data = resp.json()
                return data.get("body") or ""

        # Fallback: fetch the HTML page
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(
                html_url,
                headers={"User-Agent": "pia/1.0 (product intelligence agent)"},
            )
            resp.raise_for_status()
            return resp.text
