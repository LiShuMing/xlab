"""MBPP dataset.

Source: HuggingFace `google-research-datasets/mbpp` (full config)
Size: ~500 test problems (mostly Python programming tasks).
License: CC-BY 4.0
"""

from __future__ import annotations

from llm_benchmark.datasets.base import Dataset, register_dataset


@register_dataset("mbpp")
class MBPPDataset(Dataset):
    """MBPP: Mostly Basic Python Programming benchmark."""

    name = "mbpp"

    def __init__(self, max_samples: int | None = None):
        self._data: list[dict] = []
        self._max_samples = max_samples

    def load(self) -> None:
        from datasets import load_dataset as hf_load

        ds = hf_load(
            "google-research-datasets/mbpp",
            "full",
            split="test",
        )
        self._data = list(ds)
        if self._max_samples:
            self._data = self._data[: self._max_samples]

    def __len__(self) -> int:
        return len(self._data)

    def get_prompt(self, idx: int) -> str:
        desc = self._data[idx]["text"]
        return (
            "Write a Python function that satisfies the following description.\n\n"
            f"{desc}\n\n"
            "```python\n"
        )

    def get_reference(self, idx: int) -> str:
        return self._data[idx]["code"]

    def get_test_cases(self, idx: int) -> list[str]:
        """Return test cases as assert statements."""
        test_list = self._data[idx]["test_list"]
        return [f"assert {t}" if not t.startswith("assert ") else t for t in test_list]

    def get_metadata(self, idx: int) -> dict:
        return {
            "task_id": self._data[idx].get("task_id", idx),
        }

    def get_category(self) -> str:
        return "code"
