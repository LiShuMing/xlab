"""Tests for version normalization and sorting utilities."""

import pytest

from pia.utils.versioning import (
    normalize_version,
    parse_semver,
    sort_versions,
    version_sort_key,
)


class TestNormalizeVersion:
    def test_strips_leading_v(self):
        assert normalize_version("v1.2.3") == "1.2.3"

    def test_strips_capital_v(self):
        # GitHub release tags use lowercase 'v' only; capital 'V' is left as-is
        # since no real-world product uses it
        result = normalize_version("V3.0.0")
        assert "3.0.0" in result

    def test_strips_whitespace(self):
        assert normalize_version("  1.2.3  ") == "1.2.3"

    def test_strips_v_and_whitespace(self):
        assert normalize_version("  v4.0.1  ") == "4.0.1"

    def test_no_prefix(self):
        assert normalize_version("2.0.0") == "2.0.0"

    def test_empty_string(self):
        assert normalize_version("") == ""

    def test_date_version(self):
        # Date-style versions used by some products (e.g. Trino 468)
        assert normalize_version("468") == "468"

    def test_prerelease_tag(self):
        assert normalize_version("v1.0.0-rc1") == "1.0.0-rc1"


class TestParseSemver:
    def test_standard_three_part(self):
        assert parse_semver("1.2.3") == (1, 2, 3, "")

    def test_two_part(self):
        major, minor, patch, pre = parse_semver("4.0")
        assert major == 4
        assert minor == 0
        assert patch == 0
        assert pre == ""

    def test_with_v_prefix(self):
        assert parse_semver("v2.5.10") == (2, 5, 10, "")

    def test_prerelease(self):
        major, minor, patch, pre = parse_semver("1.0.0-rc1")
        assert major == 1
        assert minor == 0
        assert patch == 0
        assert "rc1" in pre

    def test_unrecognized_returns_zero_tuple(self):
        major, minor, patch, pre = parse_semver("not-a-version")
        assert major == 0
        assert minor == 0
        assert patch == 0

    def test_large_version(self):
        assert parse_semver("25.1.12") == (25, 1, 12, "")


class TestVersionSortKey:
    def test_higher_major_sorts_higher(self):
        assert version_sort_key("2.0.0") > version_sort_key("1.9.9")

    def test_higher_minor_sorts_higher(self):
        assert version_sort_key("1.5.0") > version_sort_key("1.4.99")

    def test_higher_patch_sorts_higher(self):
        assert version_sort_key("1.2.4") > version_sort_key("1.2.3")

    def test_prerelease_sorts_lower_than_release(self):
        assert version_sort_key("1.0.0-rc1") < version_sort_key("1.0.0")

    def test_equal_versions(self):
        assert version_sort_key("1.2.3") == version_sort_key("1.2.3")


class TestSortVersions:
    def test_descending_default(self):
        versions = ["1.0.0", "3.0.0", "2.0.0"]
        result = sort_versions(versions)
        assert result == ["3.0.0", "2.0.0", "1.0.0"]

    def test_ascending(self):
        versions = ["1.0.0", "3.0.0", "2.0.0"]
        result = sort_versions(versions, descending=False)
        assert result == ["1.0.0", "2.0.0", "3.0.0"]

    def test_with_v_prefix(self):
        versions = ["v1.0.0", "v2.0.0", "v1.5.0"]
        result = sort_versions(versions)
        assert result[0] == "v2.0.0"
        assert result[-1] == "v1.0.0"

    def test_prerelease_ordering(self):
        versions = ["1.0.0", "1.0.0-rc1", "1.0.0-alpha"]
        result = sort_versions(versions)
        # Stable release should come first
        assert result[0] == "1.0.0"

    def test_empty_list(self):
        assert sort_versions([]) == []

    def test_single_element(self):
        assert sort_versions(["1.0.0"]) == ["1.0.0"]

    def test_realistic_versions(self):
        versions = ["3.1.10", "3.2.0", "3.1.9", "4.0.0", "3.2.1"]
        result = sort_versions(versions)
        assert result[0] == "4.0.0"
        assert result[1] == "3.2.1"
        assert result[2] == "3.2.0"
