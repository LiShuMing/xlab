"""Prompt management module for external prompt files.

This module implements Harness Engineering Rule 4.1: External Prompt Management.
Prompts are stored in external files with version tracking for A/B testing
and hot-reloading support.
"""

import json
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from dbradar.logging_config import get_logger

logger = get_logger(__name__)

# Default prompts directory
DEFAULT_PROMPTS_DIR = Path(__file__).parent / "prompts"


class PromptVersion(BaseModel):
    """Single prompt version definition."""

    file: str
    description: str
    created_at: str
    variables: list[str] = Field(default_factory=list)


class PromptEntry(BaseModel):
    """Prompt entry with version tracking."""

    current_version: str
    versions: dict[str, PromptVersion]


class PromptRegistry(BaseModel):
    """Full prompt registry."""

    version: str
    prompts: dict[str, PromptEntry]


class PromptLoader:
    """Load and manage prompts from external files.

    Supports:
    - Version tracking for A/B testing
    - Variable substitution
    - Hot-reloading (reload on each load call)
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or DEFAULT_PROMPTS_DIR
        self._registry: Optional[PromptRegistry] = None
        self._prompt_cache: dict[str, str] = {}

    def _load_registry(self) -> PromptRegistry:
        """Load the prompt registry from YAML file."""
        registry_path = self.prompts_dir / "registry.yaml"
        if not registry_path.exists():
            raise FileNotFoundError(f"Prompt registry not found: {registry_path}")

        with open(registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return PromptRegistry.model_validate(data)

    def get_registry(self) -> PromptRegistry:
        """Get the current prompt registry (cached)."""
        if self._registry is None:
            self._registry = self._load_registry()
        return self._registry

    def reload_registry(self) -> PromptRegistry:
        """Reload the prompt registry from disk."""
        self._registry = self._load_registry()
        self._prompt_cache.clear()
        logger.debug("prompt_registry_reloaded")
        return self._registry

    def load_prompt(
        self,
        prompt_name: str,
        version: Optional[str] = None,
        variables: Optional[dict[str, Any]] = None,
    ) -> str:
        """Load a prompt with optional variable substitution.

        Args:
            prompt_name: Name of the prompt in the registry
            version: Specific version to load (None = current version)
            variables: Variables to substitute in the prompt

        Returns:
            The prompt text with variables substituted

        Raises:
            KeyError: If prompt_name or version not found
            FileNotFoundError: If prompt file not found
        """
        registry = self.get_registry()

        if prompt_name not in registry.prompts:
            raise KeyError(f"Prompt not found in registry: {prompt_name}")

        entry = registry.prompts[prompt_name]
        version = version or entry.current_version

        if version not in entry.versions:
            raise KeyError(
                f"Version {version} not found for prompt {prompt_name}. "
                f"Available: {list(entry.versions.keys())}"
            )

        version_info = entry.versions[version]

        # Check cache
        cache_key = f"{prompt_name}:{version}"
        if cache_key in self._prompt_cache:
            prompt_text = self._prompt_cache[cache_key]
        else:
            # Load from file
            prompt_path = self.prompts_dir / version_info.file
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()

            self._prompt_cache[cache_key] = prompt_text

        # Substitute variables
        if variables:
            prompt_text = self._substitute_variables(prompt_text, variables)

        logger.debug(
            "prompt_loaded",
            prompt_name=prompt_name,
            version=version,
            variables=list(variables.keys()) if variables else [],
        )

        return prompt_text

    def _substitute_variables(self, prompt_text: str, variables: dict[str, Any]) -> str:
        """Substitute variables in prompt text.

        Uses {{variable_name}} syntax for substitution.
        JSON values are automatically serialized.
        """
        result = prompt_text
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            if isinstance(value, (dict, list)):
                # Serialize JSON values
                str_value = json.dumps(value, indent=2, ensure_ascii=False)
            else:
                str_value = str(value)
            result = result.replace(placeholder, str_value)
        return result

    def get_prompt_version(self, prompt_name: str) -> str:
        """Get the current version of a prompt (for tracking)."""
        registry = self.get_registry()
        if prompt_name not in registry.prompts:
            raise KeyError(f"Prompt not found: {prompt_name}")
        return registry.prompts[prompt_name].current_version

    def list_prompts(self) -> dict[str, str]:
        """List all available prompts with their current versions."""
        registry = self.get_registry()
        return {
            name: entry.current_version
            for name, entry in registry.prompts.items()
        }


# Global prompt loader instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get the global prompt loader instance."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def load_prompt(
    prompt_name: str,
    version: Optional[str] = None,
    variables: Optional[dict[str, Any]] = None,
) -> str:
    """Convenience function to load a prompt.

    Args:
        prompt_name: Name of the prompt in the registry
        version: Specific version to load (None = current version)
        variables: Variables to substitute in the prompt

    Returns:
        The prompt text with variables substituted
    """
    loader = get_prompt_loader()
    return loader.load_prompt(prompt_name, version, variables)
