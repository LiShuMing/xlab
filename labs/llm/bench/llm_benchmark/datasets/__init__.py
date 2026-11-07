"""Benchmark datasets — auto-import all registered datasets.

Importing this package registers all dataset classes in the global REGISTRY.
"""

from llm_benchmark.datasets.base import Dataset, REGISTRY, build_dataset, list_datasets, register_dataset  # noqa: F401
from llm_benchmark.datasets import math_dataset  # noqa: F401
from llm_benchmark.datasets import gsm8k_dataset  # noqa: F401
from llm_benchmark.datasets import humaneval_dataset  # noqa: F401
from llm_benchmark.datasets import mbpp_dataset  # noqa: F401