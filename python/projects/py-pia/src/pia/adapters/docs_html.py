"""HTML documentation page adapter for release discovery."""

import re
import structlog
import httpx
from bs4 import BeautifulSoup

from pia.adapters.base import BaseAdapter
from pia.models.product import Product, ProductSource
from pia.models.release import Release
from pia.utils.dates import now_utc, parse_date
from pia.utils.hashing import hash_content, hash_url
from pia.utils.versioning import normalize_version

log = structlog.get_logger()

# Pattern matching typical semver or date-based version strings found in headings/links
VERSION_PATTERN = re.compile(
    r"\b(\d+\.\d+[\.\d]*(?:[-\.][a-zA-Z0-9]+)?)\b"
)


class DocsHtmlAdapter(BaseAdapter):
    """Fetches releases from an HTML documentation page.

    Parses h2/h3 headings and anchor links for version-like strings
    to discover available releases from a static changelog/docs page.
    """

    async def fetch_releases(self, product: Product, source: ProductSource) -> list[Release]:
        """Discover releases by scraping version headings/links from an HTML page.

        Args:
            product: Product configuration.
            source: Source config with the docs URL.

        Returns:
            List of Release objects discovered from the page.
        """
        html = await self._get_html(source.url)
        soup = BeautifulSoup(html, "lxml")

        seen_versions: set[str] = set()
        releases: list[Release] = []

        # Look for version-like headings (h2, h3)
        for heading in soup.find_all(["h2", "h3"]):
            text = heading.get_text(strip=True)
            match = VERSION_PATTERN.search(text)
            if not match:
                continue
            raw_version = match.group(1)
            version = normalize_version(raw_version)
            if version in seen_versions:
                continue
            seen_versions.add(version)

            # Try to find an anchor link near the heading
            link = heading.find("a", href=True)
            href = link.get("href", "") if link else ""
            if href and not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(source.url, href)
            if not href:
                href = source.url

            release_id = f"{product.id}-{re.sub(r'[^a-z0-9.-]', '-', version.lower())}"
            releases.append(
                Release(
                    id=release_id,
                    product_id=product.id,
                    version=version,
                    title=text,
                    published_at=None,
                    source_url=href,
                    source_type="docs_html",
                    source_hash=hash_content(text),
                    discovered_at=now_utc(),
                )
            )

        # Also look for links with version-like text
        if not releases:
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                match = VERSION_PATTERN.match(text)
                if not match:
                    continue
                raw_version = match.group(1)
                version = normalize_version(raw_version)
                if version in seen_versions:
                    continue
                seen_versions.add(version)

                href = a.get("href", "")
                if href and not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(source.url, href)

                release_id = f"{product.id}-{re.sub(r'[^a-z0-9.-]', '-', version.lower())}"
                releases.append(
                    Release(
                        id=release_id,
                        product_id=product.id,
                        version=version,
                        title=text,
                        published_at=None,
                        source_url=href or source.url,
                        source_type="docs_html",
                        source_hash=hash_content(text),
                        discovered_at=now_utc(),
                    )
                )

        log.info(
            "docs_html releases discovered",
            product=product.id,
            count=len(releases),
            url=source.url,
        )
        return releases[:30]

    async def fetch_release_content(self, release: Release) -> str:
        """Fetch the full HTML content of the release page.

        Args:
            release: Release whose content to fetch.

        Returns:
            Raw HTML string.
        """
        return await self._get_html(release.source_url)

    async def _get_html(self, url: str) -> str:
        """Download an HTML page.

        Args:
            url: URL to fetch.

        Returns:
            Response body as a string.
        """
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "pia/1.0 (product intelligence agent)"},
            )
            resp.raise_for_status()
            return resp.text
