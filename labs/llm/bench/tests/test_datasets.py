"""Tests for datasets — base, registry, and dataset implementations."""

from __future__ import annotations

import pytest

from llm_benchmark.datasets.base import Dataset, REGISTRY, build_dataset, list_datasets, register_dataset


class TestRegistry:
    def test_register_and_build(self):
        @register_dataset("test_math")
        class _TestDS(Dataset):
            name = "test_math"

            def load(self):
                self._data = [{"q": "1+1", "a": "2"}]

            def __len__(self):
                return len(self._data)

            def get_prompt(self, idx):
                return self._data[idx]["q"]

            def get_reference(self, idx):
                return self._data[idx]["a"]

        ds = build_dataset("test_math")
        ds.load()
        assert len(ds) == 1
        assert ds.get_prompt(0) == "1+1"
        assert ds.get_reference(0) == "2"

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown dataset"):
            build_dataset("nonexistent_dataset_xyz")

    def test_list_datasets(self):
        names = list_datasets()
        # At least the 4 built-in datasets should be registered
        assert "math" in names
        assert "gsm8k" in names
        assert "humaneval" in names
        assert "mbpp" in names


class TestMathDataset:
    def test_dataset_metadata(self):
        from llm_benchmark.datasets.math_dataset import MathDataset

        ds = MathDataset(max_samples=1)
        # Can't load without HF access, but can verify structure
        assert ds.name == "math"
        assert ds.get_category() == "math"


class TestGSM8KDataset:
    def test_extract_answer(self):
        from llm_benchmark.datasets.gsm8k_dataset import _extract_gsm8k_answer

        assert _extract_gsm8k_answer("The answer is 42. #### 42") == "42"
        assert _extract_gsm8k_answer("#### 1,234") == "1234"
        assert _extract_gsm8k_answer("Plain text") == "Plain text"


class TestHumanEvalDataset:
    def test_dataset_metadata(self):
        from llm_benchmark.datasets.humaneval_dataset import HumanEvalDataset

        ds = HumanEvalDataset(max_samples=1)
        assert ds.name == "humaneval"
        assert ds.get_category() == "code"


class TestMBPPDataset:
    def test_dataset_metadata(self):
        from llm_benchmark.datasets.mbpp_dataset import MBPPDataset

        ds = MBPPDataset(max_samples=1)
        assert ds.name == "mbpp"
        assert ds.get_category() == "code"