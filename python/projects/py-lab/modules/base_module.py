"""
Abstract base class for all AI Lab Platform modules.

Each module must inherit from BaseModule and implement the render() method.
Provides auto-registration via decorator pattern.
"""

from abc import ABC, abstractmethod
from typing import Any

import streamlit as st

from utils.logger import get_logger

logger = get_logger(__name__)


class BaseModule(ABC):
    """
    Abstract base class for all platform modules.
    
    Modules are automatically discovered and registered via the @register_module
    decorator. Each module provides a self-contained feature with its own UI.
    
    Attributes:
        name: Module display name for sidebar navigation
        description: Brief module description
        icon: Emoji icon for visual identification
        order: Sort order in sidebar (lower = higher in list)
    """
    
    name: str = "Base Module"
    description: str = "Base module description"
    icon: str = "🔧"
    order: int = 100
    
    def __init__(self) -> None:
        """Initialize module with session state if needed."""
        self.logger = get_logger(f"module.{self.__class__.__name__}")
        self._init_session_state()
        self.logger.debug("module_initialized", name=self.name)
    
    def _init_session_state(self) -> None:
        """Initialize module-specific session state variables."""
        session_key = f"module_{self.name.lower().replace(' ', '_')}_initialized"
        if session_key not in st.session_state:
            st.session_state[session_key] = True
            self._on_first_load()
    
    def _on_first_load(self) -> None:
        """
        Hook for one-time initialization. Override in subclass.
        
        This is called once when the module is first loaded in a session.
        Use it to initialize default values or load initial data.
        """
        pass
    
    @abstractmethod
    def render(self) -> None:
        """
        Main render method called by the application router.
        
        Must be implemented by all modules. This method should:
        1. Call self.display_header() to show module header
        2. Implement the module's UI and functionality
        3. Handle user interactions
        
        Example:
            >>> def render(self) -> None:
            ...     self.display_header()
            ...     user_input = st.text_input("Enter something:")
            ...     if st.button("Submit"):
            ...         self.process_input(user_input)
        """
        pass
    
    def get_full_name(self) -> str:
        """
        Get full module name with icon.
        
        Returns:
            Formatted name like "🧪 Sandbox"
        """
        return f"{self.icon} {self.name}"
    
    def display_header(self) -> None:
        """
        Display standard module header.
        
        Shows the module icon, name, and description with consistent styling.
        Should be called at the start of render() in subclasses.
        """
        st.header(f"{self.icon} {self.name}")
        if self.description:
            st.caption(self.description)
        st.divider()
    
    def show_error(self, message: str, exception: Exception | None = None) -> None:
        """
        Display an error message with optional exception logging.
        
        Args:
            message: User-facing error message
            exception: Optional exception to log
        """
        st.error(message)
        if exception:
            self.logger.error(
                "module_error",
                message=message,
                error_type=type(exception).__name__,
                error=str(exception)
            )
        else:
            self.logger.error("module_error", message=message)
    
    def show_success(self, message: str) -> None:
        """
        Display a success message.
        
        Args:
            message: Success message to display
        """
        st.success(message)
        self.logger.info("module_success", message=message)


class ModuleRegistry:
    """
    Registry for auto-discovering and managing modules.
    
    Modules register themselves via the @register_module decorator,
    and the router can enumerate them for the sidebar.
    
    Example:
        >>> @register_module
        ... class MyModule(BaseModule):
        ...     name = "My Module"
        ...     def render(self) -> None:
        ...         st.write("Hello!")
    """
    
    _modules: dict[str, BaseModule] = {}
    
    @classmethod
    def register(cls, module_class: type[BaseModule]) -> type[BaseModule]:
        """
        Decorator to register a module class.
        
        Usage:
            @ModuleRegistry.register
            class MyModule(BaseModule):
                ...
        
        Args:
            module_class: Class inheriting from BaseModule
            
        Returns:
            The same class (for decorator chaining)
        """
        instance = module_class()
        cls._modules[instance.name] = instance
        logger.info(
            "module_registered",
            name=instance.name,
            order=instance.order,
            class_name=module_class.__name__
        )
        return module_class
    
    @classmethod
    def get_modules(cls) -> dict[str, BaseModule]:
        """
        Get all registered modules sorted by order.
        
        Returns:
            Dictionary mapping module names to instances, sorted by order
        """
        return dict(
            sorted(cls._modules.items(), key=lambda x: x[1].order)
        )
    
    @classmethod
    def get_module_names(cls) -> list[str]:
        """
        Get list of module display names with icons.
        
        Returns:
            List of formatted names like ["🧪 Sandbox", "📈 Stock Analyzer"]
        """
        modules = cls.get_modules()
        return [m.get_full_name() for m in modules.values()]
    
    @classmethod
    def get_module_by_name(cls, full_name: str) -> BaseModule | None:
        """
        Get module instance by its full name (with icon).
        
        Args:
            full_name: Full module name like "🧪 Sandbox"
            
        Returns:
            Module instance or None if not found
        """
        for module in cls._modules.values():
            if module.get_full_name() == full_name:
                return module
        return None
    
    @classmethod
    def get_module_by_simple_name(cls, name: str) -> BaseModule | None:
        """
        Get module instance by its simple name (without icon).
        
        Args:
            name: Simple module name like "Sandbox"
            
        Returns:
            Module instance or None if not found
        """
        return cls._modules.get(name)
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered modules. Mainly for testing.
        """
        cls._modules.clear()
        logger.info("registry_cleared")
    
    @classmethod
    def count(cls) -> int:
        """
        Get number of registered modules.
        
        Returns:
            Number of registered modules
        """
        return len(cls._modules)


def register_module(module_class: type[BaseModule]) -> type[BaseModule]:
    """
    Convenience decorator for module registration.
    
    Args:
        module_class: Class inheriting from BaseModule
    
    Returns:
        The same class (for decorator chaining)
    
    Example:
        >>> @register_module
        ... class MyModule(BaseModule):
        ...     name = "My Module"
        ...     description = "Does something cool"
        ...     icon = "🚀"
        ...     order = 50
        ...     
        ...     def render(self) -> None:
        ...         self.display_header()
        ...         st.write("Hello, World!")
    """
    return ModuleRegistry.register(module_class)
