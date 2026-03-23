"""
LLM summarization module.

Uses an OpenAI-compatible client, so it works with:
- Ollama (default): LLM_BASE_URL=http://localhost:11434/v1, LLM_API_KEY=ollama
- OpenAI:           LLM_BASE_URL=https://api.openai.com/v1,  LLM_API_KEY=sk-...
- Any other OpenAI-compatible endpoint (vLLM, LMStudio, etc.)

Output contract: EmailSummary is a Pydantic model. The model is asked to return
pure JSON; we strip markdown fences defensively in case the model disobeys.

Error handling:
- Retries on transient errors (rate limits, timeouts) with exponential backoff
- Validates LLM output before returning
- Logs full request/response at DEBUG level for debugging
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from openai import APIError, APIConnectionError, RateLimitError
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from my_email.config import settings

log = structlog.get_logger()


# ── custom exceptions ─────────────────────────────────────────────────────────

class LLMSummarizationError(Exception):
    """Base exception for LLM summarization failures."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class LLMOutputValidationError(LLMSummarizationError):
    """Raised when LLM output cannot be parsed or validated."""

    def __init__(self, raw_output: str, validation_error: ValidationError) -> None:
        super().__init__(
            f"LLM output validation failed: {validation_error}",
            validation_error,
        )
        self.raw_output = raw_output


class LLMConnectionError(LLMSummarizationError):
    """Raised when connection to LLM endpoint fails after retries."""

    def __init__(self, original_error: APIConnectionError) -> None:
        super().__init__(
            f"Failed to connect to LLM endpoint after retries: {original_error}",
            original_error,
        )


# ── output schema ─────────────────────────────────────────────────────────────

class EmailSummary(BaseModel):
    """Structured summary of an email newsletter."""

    title: str = Field(description="Clean title of the email or newsletter issue")
    sender_org: str = Field(description="Organization or project name, e.g. 'Apache Iceberg'")
    topics: list[str] = Field(description="3–8 main technical topic keywords")
    summary: str = Field(description="5–8 sentence detailed factual summary of the content")
    key_points: list[str] = Field(description="5–10 concrete bullet points worth remembering")
    relevance: str = Field(description='"high" | "medium" | "low" — for data/infra engineering')
    action_items: list[str] = Field(
        default_factory=list,
        description="Action items, deadlines, or decisions requiring attention (if any)",
    )
    people_mentioned: list[str] = Field(
        default_factory=list,
        description="Key people, authors, or maintainers mentioned",
    )
    links: list[str] = Field(
        default_factory=list,
        description="Important URLs, PRs, issues, or references mentioned",
    )


# ── prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a technical digest assistant for a senior data/infrastructure engineer.
Read the email below and extract structured information.
Be precise and factual. Focus on technical content — ignore marketing, unsubscribe links, and boilerplate.
Return ONLY valid JSON. No markdown fences. No explanation."""

_USER_TEMPLATE = """\
Subject: {subject}
From: {sender}
Date: {date}

Body:
{body}

Return a JSON object with exactly these fields:
- title            (string) clean, descriptive title
- sender_org       (string) organization or project name
- topics           (array of strings) 3–8 technical keywords
- summary          (string) 5–8 sentence detailed factual summary, include context and implications
- key_points       (array of strings) 5–10 concrete bullet points with technical details, numbers, and specifics
- relevance        (string) "high" | "medium" | "low" — relevance to data engineering / distributed systems
- action_items     (array of strings) deadlines, decisions, or action items (empty if none)
- people_mentioned (array of strings) key people, authors, maintainers mentioned (empty if none)
- links            (array of strings) URLs, PR numbers, issue references (empty if none)

Be thorough and specific. Include technical details, metrics, and concrete examples when available.
JSON only."""

_THREAD_SYSTEM_PROMPT = """\
You are a technical digest assistant for a senior data/infrastructure engineer.
You are analyzing an EMAIL THREAD (multiple related messages).
Synthesize the entire thread into a single coherent summary.
Focus on:
1. The main topic and evolution of the discussion
2. Key decisions, conclusions, or outcomes
3. Action items or next steps mentioned
4. Consensus or disagreements among participants
Be precise and factual. Focus on technical content.
Return ONLY valid JSON. No markdown fences. No explanation."""

_THREAD_USER_TEMPLATE = """\
Thread Subject: {subject}
Number of Messages: {message_count}
Date Range: {date_range}

{body}

Return a JSON object with exactly these fields:
- title            (string) clean, descriptive title for the entire thread
- sender_org       (string) primary organization or project name
- topics           (array of strings) 3–8 technical keywords covering the thread
- summary          (string) 5–10 sentence summary of the entire thread, including:
                   * What was discussed
                   * Key points raised by different participants
                   * Any conclusions or decisions reached
                   * Evolution of the discussion
- key_points       (array of strings) 5–10 concrete bullet points from the entire thread
- relevance        (string) "high" | "medium" | "low" — relevance to data engineering / distributed systems
- action_items     (array of strings) any action items, deadlines, or next steps (empty if none)
- people_mentioned (array of strings) key participants and people mentioned (empty if none)
- links            (array of strings) URLs, PRs, issues referenced (empty if none)

Synthesize information across all messages. Don't just list each message separately.
JSON only."""


# ── client ────────────────────────────────────────────────────────────────────

def _build_client() -> OpenAI:
    """
    Build an OpenAI client with configured settings.

    Returns:
        Configured OpenAI client instance.
    """
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if the model adds them despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _validate_relevance(value: str) -> str:
    """Validate and normalize relevance field."""
    normalized = value.lower().strip()
    if normalized not in ("high", "medium", "low"):
        raise ValueError(f"Invalid relevance value: {value}. Must be 'high', 'medium', or 'low'.")
    return normalized


# ── public API ────────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _call_llm_with_retry(
    client: OpenAI,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    """
    Call LLM API with retry logic for transient errors.

    Args:
        client: OpenAI client instance.
        model: Model identifier.
        messages: Chat messages.

    Returns:
        Raw response content.

    Raises:
        RateLimitError: If rate limit exceeded after retries.
        APIConnectionError: If connection fails after retries.
        APIError: For other API errors.
    """
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
    )
    return response.choices[0].message.content or ""


def summarize_message(subject: str, sender: str, date: str, body: str) -> EmailSummary:
    """
    Call the configured LLM and return a structured EmailSummary.

    Implements retry logic with exponential backoff for transient errors.
    Logs full request/response at DEBUG level for debugging.

    Args:
        subject: Email subject line.
        sender: Email sender address.
        date: Email date string.
        body: Email body text.

    Returns:
        Validated EmailSummary object.

    Raises:
        LLMOutputValidationError: If output cannot be parsed or validated.
        LLMConnectionError: If connection fails after retries.
        LLMSummarizationError: For other LLM-related errors.
    """
    client = _build_client()
    prompt = _USER_TEMPLATE.format(
        subject=subject, sender=sender, date=date, body=body
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    log.info("llm.summarize.start", model=settings.llm_model, subject=subject[:80])
    log.debug("llm.summarize.request", messages=messages)

    try:
        raw = _call_llm_with_retry(client, settings.llm_model, messages)
    except APIConnectionError as e:
        log.error("llm.summarize.connection_error", error=str(e))
        raise LLMConnectionError(e) from e
    except RateLimitError as e:
        log.error("llm.summarize.rate_limit", error=str(e))
        raise LLMSummarizationError(f"Rate limit exceeded: {e}", e) from e
    except APIError as e:
        log.error("llm.summarize.api_error", error=str(e))
        raise LLMSummarizationError(f"LLM API error: {e}", e) from e

    log.debug("llm.summarize.raw_response", raw=raw)

    raw = _strip_fences(raw)

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("llm.summarize.json_error", raw=raw[:500], error=str(e))
        raise LLMOutputValidationError(raw, ValidationError.from_exception_data("EmailSummary", [])) from e

    # Normalize relevance before validation
    if "relevance" in parsed:
        try:
            parsed["relevance"] = _validate_relevance(parsed["relevance"])
        except ValueError:
            log.warning("llm.summarize.invalid_relevance", value=parsed.get("relevance"))

    try:
        result = EmailSummary(**parsed)
    except ValidationError as e:
        log.error("llm.summarize.validation_error", parsed=parsed, error=str(e))
        raise LLMOutputValidationError(raw, e) from e

    log.info(
        "llm.summarize.done",
        title=result.title[:60],
        relevance=result.relevance,
        topics=result.topics,
    )
    return result


def summarize_thread(
    subject: str,
    message_count: int,
    date_range: tuple[str, str],
    combined_body: str,
) -> EmailSummary:
    """
    Summarize an email thread (multiple related messages).

    Uses specialized prompts designed for thread analysis, focusing on
    discussion evolution, key decisions, and consensus among participants.

    Args:
        subject: Thread subject (base subject without Re:/Fwd: prefixes).
        message_count: Number of messages in the thread.
        date_range: Tuple of (earliest_date, latest_date).
        combined_body: Pre-formatted combined body from ThreadAggregator.

    Returns:
        Validated EmailSummary object representing the entire thread.

    Raises:
        LLMOutputValidationError: If output cannot be parsed or validated.
        LLMConnectionError: If connection fails after retries.
        LLMSummarizationError: For other LLM-related errors.
    """
    client = _build_client()
    date_range_str = f"{date_range[0]} to {date_range[1]}"
    prompt = _THREAD_USER_TEMPLATE.format(
        subject=subject,
        message_count=message_count,
        date_range=date_range_str,
        body=combined_body,
    )
    messages = [
        {"role": "system", "content": _THREAD_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    log.info(
        "llm.summarize_thread.start",
        model=settings.llm_model,
        subject=subject[:80],
        message_count=message_count,
    )
    log.debug("llm.summarize_thread.request", messages=messages)

    try:
        raw = _call_llm_with_retry(client, settings.llm_model, messages)
    except APIConnectionError as e:
        log.error("llm.summarize_thread.connection_error", error=str(e))
        raise LLMConnectionError(e) from e
    except RateLimitError as e:
        log.error("llm.summarize_thread.rate_limit", error=str(e))
        raise LLMSummarizationError(f"Rate limit exceeded: {e}", e) from e
    except APIError as e:
        log.error("llm.summarize_thread.api_error", error=str(e))
        raise LLMSummarizationError(f"LLM API error: {e}", e) from e

    log.debug("llm.summarize_thread.raw_response", raw=raw)

    raw = _strip_fences(raw)

    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("llm.summarize_thread.json_error", raw=raw[:500], error=str(e))
        raise LLMOutputValidationError(raw, ValidationError.from_exception_data("EmailSummary", [])) from e

    # Normalize relevance before validation
    if "relevance" in parsed:
        try:
            parsed["relevance"] = _validate_relevance(parsed["relevance"])
        except ValueError:
            log.warning("llm.summarize_thread.invalid_relevance", value=parsed.get("relevance"))

    try:
        result = EmailSummary(**parsed)
    except ValidationError as e:
        log.error("llm.summarize_thread.validation_error", parsed=parsed, error=str(e))
        raise LLMOutputValidationError(raw, e) from e

    log.info(
        "llm.summarize_thread.done",
        title=result.title[:60],
        relevance=result.relevance,
        topics=result.topics,
        message_count=message_count,
    )
    return result