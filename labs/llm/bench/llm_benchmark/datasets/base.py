"""Abstract base dataset and registry system.

Extensible design: new datasets subclass Dataset and decorate with @register_dataset.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Global dataset registry: name -> Dataset subclass
REGISTRY: dict[str, type["Dataset"]] = {}


def register_dataset(name: str):
    """Decorator to register a Dataset subclass."""

    def wrapper(cls: type[Dataset]):
        REGISTRY[name] = cls
        return cls

    return wrapper


def build_dataset(name: str, **kwargs: Any) -> Dataset:
    """Factory: instantiate a registered dataset by name.

    Raises ValueError if the name is not registered.
    """
    if name not in REGISTRY:
        available = ", ".join(sorted(REGISTRY.keys()))
        raise ValueError(f"Unknown dataset '{name}'. Available: {available}")
    return REGISTRY[name](**kwargs)


def list_datasets() -> list[str]:
    """Return sorted list of registered dataset names."""
    return sorted(REGISTRY.keys())


class Dataset(ABC):
    """Abstract base for all benchmark datasets.

    Subclasses must implement:
        - load()      — download and prepare data
        - __len__()   — number of samples
        - get_prompt(idx) — prompt string for the model
        - get_reference(idx) — reference answer or solution
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique dataset identifier (e.g. 'math', 'gsm8k')."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Load or download the dataset data."""
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    @abstractmethod
    def get_prompt(self, idx: int) -> str:
        """Build the prompt sent to the LLM for sample idx."""
        ...

    @abstractmethod
    def get_reference(self, idx: int) -> str:
        """Return the reference answer/solution for sample idx."""
        ...

    def get_metadata(self, idx: int) -> dict[str, Any]:
        """Return optional metadata (difficulty, category, etc.) for sample idx.

        Default: empty dict. Subclasses may override.
        """
        return {}

    def get_category(self) -> str:
        """Return the category of this dataset: 'math' or 'code'.

        Default: 'math'. Subclasses may override.
        """
        return "math"