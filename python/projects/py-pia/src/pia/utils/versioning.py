"""Version string normalization and comparison utilities."""

import re


def normalize_version(version: str) -> str:
    """Normalize a version string by stripping leading 'v' and whitespace.

    Args:
        version: Raw version string (e.g. 'v1.2.3', ' 4.0.0').

    Returns:
        Cleaned version string (e.g. '1.2.3', '4.0.0').
    """
    return version.strip().lstrip("v")


def parse_semver(version: str) -> tuple[int, int, int, str]:
    """Parse a semver-like version string into its numeric components.

    Args:
        version: Version string to parse.

    Returns:
        Tuple of (major, minor, patch, pre_release_label).
        Non-parseable strings return (0, 0, 0, original_version).
    """
    v = normalize_version(version)
    match = re.match(r"^(\d+)\.(\d+)\.?(\d*)(.*)$", v)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        pre = match.group(4).strip("-").strip()
        return (major, minor, patch, pre)
    return (0, 0, 0, v)


def version_sort_key(version: str) -> tuple:
    """Return a sort key for a version string. Higher key = newer version.

    Pre-release versions (e.g. '1.0.0-rc1') sort lower than their release
    counterparts (e.g. '1.0.0').

    Args:
        version: Version string.

    Returns:
        Tuple suitable for use with sorted().
    """
    major, minor, patch, pre = parse_semver(version)
    # pre-release sorts lower than release
    pre_rank = 0 if pre == "" else -1
    return (major, minor, patch, pre_rank)


def sort_versions(versions: list[str], descending: bool = True) -> list[str]:
    """Sort a list of version strings.

    Args:
        versions: List of version strings.
        descending: If True, newest first. Default True.

    Returns:
        Sorted list of version strings.
    """
    return sorted(versions, key=version_sort_key, reverse=descending)
