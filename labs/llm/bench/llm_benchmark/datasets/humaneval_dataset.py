"""HumanEval dataset.

Source: HuggingFace `openai/openai_humaneval`
Size: 164 Python function completion problems.
License: MIT
"""

from __future__ import annotations

from llm_benchmark.datasets.base import Dataset, register_dataset


@register_dataset("humaneval")
class HumanEvalDataset(Dataset):
    """HumanEval: Python function completion with assert-based test cases."""

    name = "humaneval"

    def __init__(self, max_samples: int | None = None):
        self._data: list[dict] = []
        self._max_samples = max_samples

    def load(self) -> None:
        from datasets import load_dataset as hf_load

        ds = hf_load("openai/openai_humaneval", split="test")
        self._data = list(ds)
        if self._max_samples:
            self._data = self._data[: self._max_samples]

    def __len__(self) -> int:
        return len(self._data)

    def get_prompt(self, idx: int) -> str:
        """HumanEval prompt is the function signature + docstring."""
        return self._data[idx]["prompt"]

    def get_reference(self, idx: int) -> str:
        return self._data[idx]["canonical_solution"]

    def get_test_cases(self, idx: int) -> list[str]:
        """Return the test case assert statements."""
        test_code = self._data[idx]["test"]
        # test is a string of the form:
        # def check(candidate):
        #     assert ...
        # We extract the assert statements and create a call to check()
        entry_point = self._data[idx]["entry_point"]
        lines = test_code.strip().split("\n")
        return [
            *lines,
            f"\ncheck({entry_point})",
        ]

    def get_metadata(self, idx: int) -> dict:
        return {
            "entry_point": self._data[idx].get("entry_point", ""),
            "task_id": self._data[idx].get("task_id", ""),
        }

    def get_category(self) -> str:
        return "code"
