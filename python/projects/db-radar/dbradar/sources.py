"""Parse and manage source URLs from websites.txt."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Source:
    """Represents a data source with product name and URLs."""

    product: str
    urls: List[str]


def parse_websites_file(file_path: Path) -> List[Source]:
    """
    Parse the websites.txt file and extract sources.

    Supports multiple line formats:
    - "Product | url1 | url2 | url3" (pipe-separated)
    - "Product url1 url2 url3" (space-separated)
    - Lines starting with # are comments
    - Blank lines are ignored

    Args:
        file_path: Path to the websites.txt file.

    Returns:
        List of Source objects.
    """
    sources: List[Source] = []

    if not file_path.exists():
        return sources

    content = file_path.read_text()
    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Try pipe-separated format first: "Product | url1 | url2"
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                product = parts[0]
                urls = [u for u in parts[1:] if u]
                if urls:
                    sources.append(Source(product=product, urls=urls))
                continue

        # Try space-separated format: "Product url1 url2 url3"
        # Assume first token is product name, rest are URLs
        tokens = line.split()
        if len(tokens) >= 2:
            product = tokens[0]
            urls = tokens[1:]
            # Filter out markdown-style links and non-URLs
            valid_urls = []
            for url in urls:
                url = url.strip().rstrip(",")
                if url.startswith("http://") or url.startswith("https://"):
                    valid_urls.append(url)
            if valid_urls:
                sources.append(Source(product=product, urls=valid_urls))

    return sources


def get_sources(website_file: Optional[Path] = None) -> List[Source]:
    """
    Convenience function to get sources from the default websites.txt.

    Args:
        website_file: Optional custom path to websites.txt.

    Returns:
        List of Source objects.
    """
    from dbradar.config import get_config

    config = get_config()
    path = website_file or config.website_file
    return parse_websites_file(path)


if __name__ == "__main__":
    # Quick test
    sources = parse_websites_file(Path("websites.txt"))
    for s in sources[:5]:
        print(f"Product: {s.product}, URLs: {len(s.urls)}")
