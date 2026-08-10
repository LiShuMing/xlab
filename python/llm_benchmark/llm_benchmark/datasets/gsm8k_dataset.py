"""GSM8K dataset.

Source: HuggingFace `gsm8k` (main config)
Size: 1,319 test problems (grade-school math word problems).
License: MIT
"""

from __future__ import annotations

import re

from llm_benchmark.datasets.base import Dataset, register_dataset


def _extract_gsm8k_answer(answer_str: str) -> str:
    """Extract the final numeric answer from GSM8K format (#### number)."""
    match = re.search(r"####\s*([\d,.\-]+)", answer_str)
    if match:
        return match.group(1).replace(",", "")
    return answer_str.strip()


@register_dataset("gsm8k")
class GSM8KDataset(Dataset):
    """GSM8K benchmark: grade-school math word problems."""

    name = "gsm8k"

    def __init__(self, max_samples: int | None = None):
        self._data: list[dict] = []
        self._max_samples = max_samples

    def load(self) -> None:
        from datasets import load_dataset as hf_load

        ds = hf_load("openai/gsm8k", "main", split="test")
        self._data = list(ds)
        if self._max_samples:
            self._data = self._data[: self._max_samples]

    def __len__(self) -> int:
        return len(self._data)

    def get_prompt(self, idx: int) -> str:
        question = self._data[idx]["question"]
        return (
            f"Question: {question}\n\n"
            "Let's solve this step by step. "
            "End your solution with the final answer after ####.\n"
        )

    def get_reference(self, idx: int) -> str:
        return _extract_gsm8k_answer(self._data[idx]["answer"])

    def get_category(self) -> str:
        return "math"
