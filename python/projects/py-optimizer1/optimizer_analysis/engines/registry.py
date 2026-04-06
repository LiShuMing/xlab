"""Engine registry for managing optimizer engine configurations."""

from typing import Dict, List

from optimizer_analysis.engines.base import EngineConfig


class EngineRegistry:
    """Registry for managing optimizer engine configurations.

    Provides methods to register, retrieve, and list engine configurations.
    """

    def __init__(self) -> None:
        """Initialize an empty engine registry."""
        self._engines: Dict[str, EngineConfig] = {}

    def register(self, config: EngineConfig) -> None:
        """Register an engine configuration.

        Args:
            config: Engine configuration to register.

        Raises:
            ValueError: If an engine with the same name already exists.
        """
        if config.name in self._engines:
            raise ValueError(f"Engine '{config.name}' is already registered")
        self._engines[config.name] = config

    def get(self, name: str) -> EngineConfig:
        """Get an engine configuration by name.

        Args:
            name: Name of the engine to retrieve.

        Returns:
            Engine configuration for the specified name.

        Raises:
            KeyError: If no engine with the given name exists.
        """
        if name not in self._engines:
            raise KeyError(f"Engine '{name}' not found in registry")
        return self._engines[name]

    def list_engines(self) -> List[str]:
        """List all registered engine names.

        Returns:
            List of engine names in the registry.
        """
        return list(self._engines.keys())

    def clear(self) -> None:
        """Clear all registered engines from the registry."""
        self._engines.clear()