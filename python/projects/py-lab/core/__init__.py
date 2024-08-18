"""Core module for AI Lab Platform."""

# Optional imports - may fail if dependencies not installed
try:
    from .llm_factory import get_llm, get_cached_llm, get_available_providers, get_embedding_model
    __all__ = ["get_llm", "get_cached_llm", "get_available_providers", "get_embedding_model"]
except ImportError:
    # Dependencies not available (e.g., in minimal test environment)
    __all__ = []
