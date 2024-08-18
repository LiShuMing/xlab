"""Prompt templates for py-cli."""

from __future__ import annotations

from typing import TYPE_CHECKING

from py_cli.exceptions import PromptNotFoundError
from py_cli.llm.prompts import clickhouse, default

if TYPE_CHECKING:
    from types import ModuleType

# Registry of available prompts
PROMPTS: dict[str, ModuleType] = {
    "default": default,
    "clickhouse": clickhouse,
}


def get_prompt(name: str) -> ModuleType:
    """Get a prompt module by name.

    Args:
        name: Prompt name

    Returns:
        Prompt module with SYSTEM_PROMPT and USER_PROMPT_TEMPLATE

    Raises:
        PromptNotFoundError: If prompt doesn't exist
    """
    if name not in PROMPTS:
        available = ", ".join(PROMPTS.keys())
        msg = f"Prompt '{name}' not found. Available: {available}"
        raise PromptNotFoundError(msg)
    return PROMPTS[name]


def list_prompts() -> list[str]:
    """List available prompt names."""
    return list(PROMPTS.keys())


def register_prompt(name: str, module: ModuleType) -> None:
    """Register a new prompt module.

    Args:
        name: Prompt name
        module: Module with SYSTEM_PROMPT and USER_PROMPT_TEMPLATE
    """
    PROMPTS[name] = module
