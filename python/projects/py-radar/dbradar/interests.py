"""Load and manage user interests configuration for personalized ranking."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class InterestsConfig:
    """
    User interests configuration for personalized ranking.

    Attributes:
        products: Dict mapping product names to boost weights (e.g., {"DuckDB": 2.0}).
        keywords: Dict mapping keywords to boost weights (e.g., {"lakehouse": 1.6}).
        raw_yaml: Original YAML file contents for display in sidebar.
    """

    products: Dict[str, float] = field(default_factory=dict)
    keywords: Dict[str, float] = field(default_factory=dict)
    raw_yaml: str = ""  # original casing preserved for display

    @classmethod
    def load(cls, path: Path) -> Optional[InterestsConfig]:
        """
        Load interests configuration from a YAML file.

        Args:
            path: Path to the interests.yaml file.

        Returns:
            InterestsConfig instance, or None if file doesn't exist or is malformed.
        """
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)

            if not isinstance(data, dict):
                warnings.warn(f"Invalid interests.yaml format: expected dict, got {type(data)}")
                return None

            # Normalize keys to lowercase for matching
            products = {
                k.lower(): float(v)
                for k, v in data.get("products", {}).items()
                if isinstance(v, (int, float))
            }

            keywords = {
                k.lower(): float(v)
                for k, v in data.get("keywords", {}).items()
                if isinstance(v, (int, float))
            }

            return cls(products=products, keywords=keywords, raw_yaml=raw)

        except yaml.YAMLError as e:
            warnings.warn(f"Failed to parse interests.yaml: {e}")
            return None

    @classmethod
    def default(cls) -> InterestsConfig:
        """Return default (empty) interests configuration."""
        return cls(products={}, keywords={}, raw_yaml="")

    def has_products(self) -> bool:
        """Check if any product priorities are defined."""
        return bool(self.products)

    def has_keywords(self) -> bool:
        """Check if any keyword boosts are defined."""
        return bool(self.keywords)