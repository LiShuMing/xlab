"""Modules package for AI Lab Platform."""

# Optional imports - may fail if dependencies not installed
try:
    from .base_module import BaseModule, ModuleRegistry, register_module
    __all__ = ["BaseModule", "ModuleRegistry", "register_module"]
except ImportError:
    # Dependencies not available (e.g., in minimal test environment)
    __all__ = []
