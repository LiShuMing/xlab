"""
LLM summarization module.

Provides structured email summarization using OpenAI-compatible APIs.
Includes email filtering and thread aggregation capabilities.
"""

from my_email.llm.email_filter import (
    EmailFilter,
    create_default_filter,
)
from my_email.llm.summarizer import (
    EmailSummary,
    LLMConnectionError,
    LLMOutputValidationError,
    LLMSummarizationError,
    summarize_message,
    summarize_thread,
)
from my_email.llm.thread_aggregator import (
    ThreadAggregator,
    create_default_aggregator,
)

__all__ = [
    # Core summarization
    "EmailSummary",
    "LLMSummarizationError",
    "LLMOutputValidationError",
    "LLMConnectionError",
    "summarize_message",
    "summarize_thread",
    # Filtering
    "EmailFilter",
    "create_default_filter",
    # Thread aggregation
    "ThreadAggregator",
    "create_default_aggregator",
]
