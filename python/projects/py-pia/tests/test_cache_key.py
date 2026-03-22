"""Tests for cache key stability and correctness."""

import pytest

from pia.utils.hashing import make_cache_key, hash_content


class TestCacheKeyStability:
    """Verify that cache keys are stable across calls with identical inputs."""

    FIXED_ARGS = (
        "starrocks",
        "4.0.6",
        "deep_analysis",
        "claude-opus-4-5",
        "v1",
        "abcdef1234567890",
    )

    def test_same_inputs_same_key(self):
        """Identical inputs must always produce the same key."""
        k1 = make_cache_key(*self.FIXED_ARGS)
        k2 = make_cache_key(*self.FIXED_ARGS)
        assert k1 == k2

    def test_key_is_not_empty(self):
        key = make_cache_key(*self.FIXED_ARGS)
        assert key
        assert len(key) > 0

    def test_key_is_hex_string(self):
        key = make_cache_key(*self.FIXED_ARGS)
        int(key, 16)  # Should not raise

    def test_key_length_is_64(self):
        """SHA-256 produces 64 hex characters."""
        key = make_cache_key(*self.FIXED_ARGS)
        assert len(key) == 64


class TestCacheKeyUniqueness:
    """Verify that different inputs produce different cache keys."""

    BASE_ARGS = {
        "product_id": "starrocks",
        "version": "4.0.0",
        "report_type": "deep_analysis",
        "model_name": "claude-opus-4-5",
        "prompt_version": "v1",
        "normalized_hash": "abc123",
    }

    def _make_key(self, **overrides) -> str:
        args = {**self.BASE_ARGS, **overrides}
        return make_cache_key(**args)

    def _base_key(self) -> str:
        return make_cache_key(**self.BASE_ARGS)

    def test_all_dimensions_matter(self):
        """Changing any single dimension changes the key."""
        base = self._base_key()

        assert self._make_key(product_id="clickhouse") != base
        assert self._make_key(version="4.0.1") != base
        assert self._make_key(report_type="summary") != base
        assert self._make_key(model_name="claude-haiku-3-5") != base
        assert self._make_key(prompt_version="v2") != base
        assert self._make_key(normalized_hash="xyz999") != base

    def test_each_dimension_independently_unique(self):
        """Each changed dimension produces a unique key from the others."""
        keys = [
            self._make_key(product_id="clickhouse"),
            self._make_key(version="4.0.1"),
            self._make_key(report_type="summary"),
            self._make_key(model_name="claude-haiku-3-5"),
            self._make_key(prompt_version="v2"),
            self._make_key(normalized_hash="xyz999"),
        ]
        # All keys should be unique
        assert len(set(keys)) == len(keys)


class TestCacheKeyWithRealHashContent:
    """Test cache key behavior when combined with hash_content."""

    def test_same_content_same_cache_key(self):
        content = "## StarRocks 4.0.0 Release Notes\n\n- Feature A\n- Feature B\n"
        norm_hash = hash_content(content)
        k1 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", norm_hash)
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", norm_hash)
        assert k1 == k2

    def test_different_content_different_cache_key(self):
        content_a = "## StarRocks 4.0.0 Release Notes\n\n- Feature A\n"
        content_b = "## StarRocks 4.0.0 Release Notes\n\n- Feature B (updated)\n"
        hash_a = hash_content(content_a)
        hash_b = hash_content(content_b)

        k_a = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", hash_a)
        k_b = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", hash_b)
        assert k_a != k_b

    def test_content_hash_uniqueness_within_product(self):
        """Two releases of the same product with different content get different keys."""
        content_v1 = "## v3.3.0 Release\n\n- New feature X"
        content_v2 = "## v4.0.0 Release\n\n- New feature Y, breaking change Z"

        h1 = hash_content(content_v1)
        h2 = hash_content(content_v2)

        k1 = make_cache_key("starrocks", "3.3.0", "deep_analysis", "claude-opus-4-5", "v1", h1)
        k2 = make_cache_key("starrocks", "4.0.0", "deep_analysis", "claude-opus-4-5", "v1", h2)

        assert k1 != k2
