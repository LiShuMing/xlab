"""Custom exceptions for py-cli."""

from __future__ import annotations


class PyCliError(Exception):
    """Base exception for all py-cli errors."""

    pass


class ConfigError(PyCliError):
    """Configuration-related errors."""

    pass


class GitError(PyCliError):
    """Git operation errors."""

    pass


class LLMError(PyCliError):
    """LLM API errors."""

    pass


class AnalysisError(PyCliError):
    """Analysis process errors."""

    pass


class PromptNotFoundError(PyCliError):
    """Requested prompt template not found."""

    pass
