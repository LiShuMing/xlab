"""Tests for content hashing utilities."""

import pytest

from pia.utils.hashing import hash_content, hash_url, make_cache_key


class TestHashContent:
    def test_returns_string(self):
        result = hash_content("hello world")
        assert isinstance(result, str)

    def test_fixed_length_16(self):
        result = hash_content("test content")
        assert len(result) == 16

    def test_deterministic(self):
        content = "This is test content for hashing."
        assert hash_content(content) == hash_content(content)

    def test_different_inputs_different_hashes(self):
        assert hash_content("content A") != hash_content("content B")

    def test_empty_string(self):
        result = hash_content("")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_unicode_content(self):
        result = hash_content("版本发布说明 StarRocks 4.0")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_whitespace_sensitivity(self):
        # A leading space changes the hash
        assert hash_content("hello") != hash_content(" hello")


class TestHashUrl:
    def test_returns_string(self):
        result = hash_url("https://example.com/releases")
        assert isinstance(result, str)

    def test_fixed_length_8(self):
        result = hash_url("https://example.com/releases")
        assert len(result) == 8

    def test_deterministic(self):
        url = "https://api.github.com/repos/StarRocks/starrocks/releases"
        assert hash_url(url) == hash_url(url)

    def test_different_urls_different_hashes(self):
        assert hash_url("https://example.com/a") != hash_url("https://example.com/b")


class TestMakeCacheKey:
    def test_returns_full_sha256(self):
        key = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "abc123")
        assert len(key) == 64  # full SHA-256 hex
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic(self):
        args = ("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "abc123")
        assert make_cache_key(*args) == make_cache_key(*args)

    def test_different_product_different_key(self):
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("clickhouse", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        assert k1 != k2

    def test_different_version_different_key(self):
        k1 = make_cache_key("starrocks", "3.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        assert k1 != k2

    def test_different_model_different_key(self):
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-haiku-3-5", "v1", "hash1")
        assert k1 != k2

    def test_different_prompt_version_different_key(self):
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v2", "hash1")
        assert k1 != k2

    def test_different_normalized_hash_different_key(self):
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash2")
        assert k1 != k2

    def test_different_report_type_different_key(self):
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", "hash1")
        k2 = make_cache_key("starrocks", "4.0.0", "summary", "claude-opus-4-5", "v1", "hash1")
        assert k1 != k2
