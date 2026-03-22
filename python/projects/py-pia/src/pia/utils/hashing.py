"""Content hashing utilities for caching and deduplication."""

import hashlib


def hash_content(content: str) -> str:
    """Compute a short SHA-256 hash of a string.

    Args:
        content: String to hash.

    Returns:
        First 16 hex characters of the SHA-256 digest.
    """
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def hash_url(url: str) -> str:
    """Compute a short MD5 hash of a URL for use as a cache filename.

    Args:
        url: URL string.

    Returns:
        First 8 hex characters of the MD5 digest.
    """
    return hashlib.md5(url.encode()).hexdigest()[:8]


def make_cache_key(
    product_id: str,
    version: str,
    report_type: str,
    model_name: str,
    prompt_version: str,
    normalized_hash: str,
) -> str:
    """Compute a stable cache key for a report.

    The cache key is derived from all inputs that affect report content,
    so any change to model, prompt, or source content will produce a new key.

    Args:
        product_id: Product identifier.
        version: Release version string.
        report_type: Type of report (e.g. 'deep_analysis').
        model_name: LLM model name used.
        prompt_version: Version string of the prompt template.
        normalized_hash: Hash of the normalized source content.

    Returns:
        Full SHA-256 hex digest of the combined inputs.
    """
    combined = f"{product_id}:{version}:{report_type}:{model_name}:{prompt_version}:{normalized_hash}"
    return hashlib.sha256(combined.encode()).hexdigest()
