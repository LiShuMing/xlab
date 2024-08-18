"""Custom exception hierarchy for the LLM research pipeline."""
from __future__ import annotations


class LLMResearchError(Exception):
    """Base exception for all pipeline errors."""


class PromptLearnerError(LLMResearchError):
    """Raised when prompt extraction fails."""


class ResearcherError(LLMResearchError):
    """Raised when API call or report generation fails."""


class ReportManagerError(LLMResearchError):
    """Raised when report persistence or manifest operations fail."""


class ServerError(LLMResearchError):
    """Raised when the FastAPI server encounters an error."""


class APIKeyMissingError(ResearcherError):
    """Raised when a required API key is not set."""


class MkDocsError(LLMResearchError):
    """Raised when MkDocs build fails."""
