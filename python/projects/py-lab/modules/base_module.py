"""
Abstract base class for all AI Lab Platform modules.
Each module must inherit from BaseModule and implement the render() method.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import streamlit as st


class BaseModule(ABC):
    """
    Abstract base class for all platform modules.
    
    Attributes:
        name: Module display name for sidebar navigation.
        description: Brief module description.
        icon: Emoji icon for visual identification.
        order: Sort order in sidebar (lower = higher).
    """
    
    name: str = "Base Module"
    description: str = "Base module description"
    icon: str = "🔧"
    order: int = 100
    
    def __init__(self):
        """Initialize module with session state if needed."""
        self._init_session_state()
    
    def _init_session_state(self) -> None:
        """Initialize module-specific session state variables."""
        session_key = f"module_{self.name.lower().replace(' ', '_')}_initialized"
        if session_key not in st.session_state:
            st.session_state[session_key] = True
            self._on_first_load()
    
    def _on_first_load(self) -> None:
        """Hook for one-time initialization. Override in subclass."""
        pass
    
    @abstractmethod
    def render(self) -> None:
        """
        Main render method called by the application router.
        Must be implemented by all modules.
        """
        pass
    
    def get_full_name(self) -> str:
        """Get full module name with icon."""
        return f"{self.icon} {self.name}"
    
    def display_header(self) -> None:
        """Display standard module header."""
        st.header(f"{self.icon} {self.name}")
        if self.description:
            st.caption(self.description)
        st.divider()


class ModuleRegistry:
    """
    Registry for auto-discovering and managing modules.
    Modules register themselves and the router can enumerate them.
    """
    
    _modules: Dict[str, BaseModule] = {}
    
    @classmethod
    def register(cls, module_class: type) -> type:
        """
        Decorator to register a module class.
        
        Usage:
            @ModuleRegistry.register
            class MyModule(BaseModule):
                ...
        """
        instance = module_class()
        cls._modules[instance.name] = instance
        return module_class
    
    @classmethod
    def get_modules(cls) -> Dict[str, BaseModule]:
        """Get all registered modules sorted by order."""
        return dict(
            sorted(cls._modules.items(), key=lambda x: x[1].order)
        )
    
    @classmethod
    def get_module_names(cls) -> list[str]:
        """Get list of module display names with icons."""
        modules = cls.get_modules()
        return [m.get_full_name() for m in modules.values()]
    
    @classmethod
    def get_module_by_name(cls, full_name: str) -> Optional[BaseModule]:
        """Get module instance by its full name (with icon)."""
        for name, module in cls._modules.items():
            if module.get_full_name() == full_name:
                return module
        return None
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered modules. Mainly for testing."""
        cls._modules.clear()


def register_module(module_class: type) -> type:
    """
    Convenience decorator for module registration.
    
    Args:
        module_class: Class inheriting from BaseModule.
    
    Returns:
        The same class (for decorator chaining).
    """
    return ModuleRegistry.register(module_class)
