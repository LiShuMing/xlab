"""MATH dataset.

Source: HuggingFace `jeggers/competition_math` (original config)
Size: 5,000 test problems across 5 difficulty levels.
License: MIT
"""

from __future__ import annotations

from llm_benchmark.datasets.base import Dataset, register_dataset


@register_dataset("math")
class MathDataset(Dataset):
    """MATH benchmark: LaTeX math problems with 5 difficulty levels."""

    name = "math"

    def __init__(self, max_samples: int | None = None):
        self._data: list[dict] = []
        self._max_samples = max_samples

    def load(self) -> None:
        from datasets import load_dataset as hf_load

        ds = hf_load("jeggers/competition_math", "original", split="test")
        self._data = list(ds)
        if self._max_samples:
            self._data = self._data[: self._max_samples]

    def __len__(self) -> int:
        return len(self._data)

    def get_prompt(self, idx: int) -> str:
        problem = self._data[idx]["problem"]
        return (
            "Solve the following math problem step by step. "
            "Put your final answer within \\boxed{}.\n\n"
            f"Problem: {problem}\n\n"
            "Solution:"
        )

    def get_reference(self, idx: int) -> str:
        """Extract the boxed answer from the solution string."""
        solution = self._data[idx]["solution"]
        # The reference solution contains \boxed{...}
        return solution.strip()

    def get_metadata(self, idx: int) -> dict:
        return {
            "level": self._data[idx].get("level", "unknown"),
            "type": self._data[idx].get("type", "unknown"),
        }

    def get_category(self) -> str:
        return "math"
