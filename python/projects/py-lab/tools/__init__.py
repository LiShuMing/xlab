"""Tools module for AI Lab Platform."""

# Optional imports - may fail if dependencies not installed
try:
    from .base_tool import BaseTool
    __all__ = ["BaseTool"]
except ImportError:
    # Dependencies not available (e.g., in minimal test environment)
    __all__ = []
