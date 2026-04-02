"""Generate structured summaries using LLM API (OpenAI-compatible).

This module implements structured output validation using Pydantic models
as per Harness Engineering standards (see RULE.md).
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

import httpx
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from dbradar.circuit_breaker import with_circuit_breaker, CircuitBreakerOpenError
from dbradar.config import get_config
from dbradar.http_client import get_http_client, LLMHttpClient
from dbradar.logging_config import get_logger, correlation_id
from dbradar.models import (
    SummaryOutput,
    TranslationOutput,
    TranslatedUpdate,
    TranslatedReleaseNote,
)
from dbradar.prompt_loader import load_prompt, get_prompt_loader
from dbradar.ranker import RankedItem

logger = get_logger(__name__)

DEFAULT_MODEL = "qwen-max"


@dataclass
class SummaryResult:
    """Result of summarization."""

    executive_summary: List[str]
    top_updates: List[dict]
    release_notes: List[dict]
    themes: List[str]
    action_items: List[str]
    raw_response: str
    validation_errors: Optional[List[str]] = None


class JSONExtractionError(Exception):
    """Raised when JSON extraction from LLM response fails."""

    pass


class ValidationFailedError(Exception):
    """Raised when Pydantic validation fails."""

    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


class Summarizer:
    """Generate structured summaries using LLM with Pydantic validation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        language: Optional[str] = None,
    ):
        config = get_config()
        self.api_key = api_key or config.api_key
        self.base_url = base_url or config.base_url
        self.model = model or config.model or DEFAULT_MODEL
        self.timeout = timeout or config.timeout
        self.language = language or config.language or "en"
        # Use the async HTTP client with connection pooling
        self.http_client = get_http_client()
        # Keep sync client for backward compatibility during transition
        self.client = httpx.Client(timeout=self.timeout)
        self.logger = get_logger(__name__)

    @with_circuit_breaker
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, "warning"),
        reraise=True,
    )
    def _call_llm(self, prompt: str, max_tokens: int = 4000) -> dict:
        """Call LLM API with retry logic (sync wrapper for async implementation).

        Args:
            prompt: The prompt to send to the LLM.
            max_tokens: Maximum tokens to generate.

        Returns:
            The raw API response data.

        Raises:
            httpx.HTTPError: If the API call fails after all retries.
            CircuitBreakerOpenError: If circuit breaker is open.
        """
        # Run the async version in an event loop for backward compatibility
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an async context, use the sync client as fallback
                return self._call_llm_sync(prompt, max_tokens)
            return loop.run_until_complete(self._call_llm_async(prompt, max_tokens))
        except RuntimeError:
            # No event loop running, create a new one
            return asyncio.run(self._call_llm_async(prompt, max_tokens))

    async def _call_llm_async(self, prompt: str, max_tokens: int = 4000) -> dict:
        """Async version of LLM API call with connection pooling.

        Args:
            prompt: The prompt to send to the LLM.
            max_tokens: Maximum tokens to generate.

        Returns:
            The raw API response data.
        """
        cid = correlation_id.get()
        log = self.logger.bind(correlation_id=cid)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        log.debug(
            "llm_request",
            url=f"{self.base_url}/chat/completions",
            model=self.model,
            max_tokens=max_tokens,
            prompt_tokens=len(prompt) // 4,
        )

        # Use the async HTTP client with connection pooling
        http_client = get_http_client()
        response = await http_client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json_payload=payload,
        )

        return response.json()

    def _call_llm_sync(self, prompt: str, max_tokens: int = 4000) -> dict:
        """Synchronous fallback using legacy httpx.Client.

        Used when called from an already-running async context.
        """
        cid = correlation_id.get()
        log = self.logger.bind(correlation_id=cid)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        log.debug(
            "llm_request_sync_fallback",
            url=f"{self.base_url}/chat/completions",
            model=self.model,
            max_tokens=max_tokens,
        )

        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _extract_json_from_response(self, raw_text: str) -> dict:
        """Extract and parse JSON from LLM response.

        Handles multiple formats:
        - Markdown code blocks (```json ... ```)
        - Raw JSON objects
        - JSON with surrounding text

        Args:
            raw_text: Raw text response from LLM.

        Returns:
            Parsed JSON as dictionary.

        Raises:
            JSONExtractionError: If JSON cannot be extracted or parsed.
        """
        if not raw_text or not raw_text.strip():
            raise JSONExtractionError("Empty response from LLM")

        json_text = raw_text.strip()

        # Try to extract from markdown code blocks
        patterns = [
            (r"```json\s*(.*?)\s*```", re.DOTALL),
            (r"```\s*(.*?)\s*```", re.DOTALL),
        ]

        for pattern, flags in patterns:
            match = re.search(pattern, json_text, flags)
            if match:
                json_text = match.group(1).strip()
                break

        # If no code blocks, try to find JSON object boundaries
        if not json_text.startswith("{"):
            start = json_text.find("{")
            if start >= 0:
                # Find matching closing brace
                brace_count = 0
                end = start
                for i, char in enumerate(json_text[start:], start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                json_text = json_text[start:end]

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            raise JSONExtractionError(f"Failed to parse JSON: {e}") from e

    def _validate_and_parse_output(self, data: dict, raw_response: str) -> SummaryResult:
        """Validate LLM output using Pydantic model.

        Args:
            data: Parsed JSON data from LLM response.
            raw_response: Original raw response for debugging.

        Returns:
            SummaryResult with validated data.

        Raises:
            ValidationFailedError: If validation fails and cannot be repaired.
        """
        validation_errors = []

        try:
            # Primary validation attempt
            validated = SummaryOutput.model_validate(data)
            return SummaryResult(
                executive_summary=validated.executive_summary,
                top_updates=[update.model_dump() for update in validated.top_updates],
                release_notes=[note.model_dump() for note in validated.release_notes],
                themes=validated.themes,
                action_items=validated.action_items,
                raw_response=raw_response,
                validation_errors=None,
            )
        except ValidationError as e:
            # Collect validation errors
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                validation_errors.append(f"{field}: {error['msg']}")

            # Attempt repair by applying defaults
            try:
                repaired = self._repair_output(data)
                validated = SummaryOutput.model_validate(repaired)
                validation_errors.append("[Repaired with defaults]")

                return SummaryResult(
                    executive_summary=validated.executive_summary,
                    top_updates=[update.model_dump() for update in validated.top_updates],
                    release_notes=[note.model_dump() for note in validated.release_notes],
                    themes=validated.themes,
                    action_items=validated.action_items,
                    raw_response=raw_response,
                    validation_errors=validation_errors,
                )
            except (ValidationError, Exception) as repair_error:
                raise ValidationFailedError(
                    f"Validation failed and repair unsuccessful: {repair_error}",
                    validation_errors,
                ) from e

    def _repair_output(self, data: dict) -> dict:
        """Attempt to repair invalid LLM output by applying defaults.

        Args:
            data: Potentially invalid output from LLM.

        Returns:
            Repaired data with defaults applied.
        """
        repaired = dict(data)

        # Ensure executive_summary exists and is non-empty
        if not repaired.get("executive_summary"):
            repaired["executive_summary"] = ["No executive summary available"]

        # Ensure lists exist
        for field in ["top_updates", "release_notes", "themes", "action_items"]:
            if field not in repaired or not isinstance(repaired[field], list):
                repaired[field] = []

        # Filter empty strings from lists
        for field in ["executive_summary", "themes", "action_items"]:
            if isinstance(repaired.get(field), list):
                repaired[field] = [
                    item for item in repaired[field]
                    if item and str(item).strip()
                ]

        # Ensure executive_summary is not empty after filtering
        if not repaired["executive_summary"]:
            repaired["executive_summary"] = ["No executive summary available"]

        # Repair top_updates entries
        if isinstance(repaired.get("top_updates"), list):
            valid_updates = []
            for update in repaired["top_updates"]:
                if isinstance(update, dict) and update.get("product") and update.get("title"):
                    valid_updates.append(update)
            repaired["top_updates"] = valid_updates

        # Repair release_notes entries
        if isinstance(repaired.get("release_notes"), list):
            valid_notes = []
            for note in repaired["release_notes"]:
                if isinstance(note, dict) and note.get("product"):
                    valid_notes.append(note)
            repaired["release_notes"] = valid_notes

        return repaired

    def _build_prompt(self, items: List[RankedItem], top_k: int = 10, force_english: bool = False) -> str:
        """Build the summarization prompt using external template."""
        # Prepare item data
        item_data = []
        for item in items[:top_k]:
            item_data.append({
                "product": item.item.product,
                "title": item.item.title,
                "url": item.item.url,
                "published_at": item.item.published_at or "unknown",
                "content_type": item.item.content_type,
                "confidence": item.item.confidence,
                "snippets": item.item.snippets[:2],
                "rank_reasons": item.reasons,
            })

        # Load external prompt with variable substitution
        prompt = load_prompt(
            "summarize",
            variables={
                "item_count": len(item_data),
                "item_data": item_data,
                "current_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
        )

        # Track prompt version for observability
        prompt_version = get_prompt_loader().get_prompt_version("summarize")
        self.logger.debug("prompt_loaded", prompt_name="summarize", version=prompt_version)

        return prompt

    def summarize(self, items: List[RankedItem], top_k: int = 10) -> SummaryResult:
        """
        Generate structured summary from ranked items with Pydantic validation.

        Args:
            items: List of ranked items.
            top_k: Number of top items to include in summary.

        Returns:
            SummaryResult with validated structured data.
        """
        cid = correlation_id.get()
        log = self.logger.bind(item_count=len(items), top_k=top_k, correlation_id=cid)

        if not items:
            log.info("summarize_empty_items")
            return SummaryResult(
                executive_summary=["No updates found for the specified period."],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response="",
                validation_errors=None,
            )

        prompt = self._build_prompt(items, top_k)
        log.debug("prompt_built", prompt_length=len(prompt))

        start_time = time.time()
        raw_text = ""

        try:
            # Call LLM with retry logic
            data = self._call_llm(prompt, max_tokens=4000)

            latency_ms = (time.time() - start_time) * 1000

            # Log LLM response (DEBUG level as per RULE.md 2.2)
            usage = data.get("usage", {})
            log.debug(
                "llm_response",
                latency_ms=round(latency_ms, 2),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
                finish_reason=data.get("choices", [{}])[0].get("finish_reason"),
            )

            # Extract response text
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
                log.error("llm_empty_response")
                return SummaryResult(
                    executive_summary=["Error: Empty response from API"],
                    top_updates=[],
                    release_notes=[],
                    themes=[],
                    action_items=[],
                    raw_response=json.dumps(data),
                    validation_errors=["Empty response from LLM"],
                )

            # Parse JSON from response using robust extraction and Pydantic validation
            parsed_data = self._extract_json_from_response(raw_text)
            result = self._validate_and_parse_output(parsed_data, raw_text)

            log.info(
                "summarize_success",
                latency_ms=round(latency_ms, 2),
                summary_count=len(result.executive_summary),
                update_count=len(result.top_updates),
                theme_count=len(result.themes),
                had_validation_errors=result.validation_errors is not None,
            )

            # If Chinese is requested, translate the result
            if self.language == "zh":
                log.debug("translation_requested", target_language="zh")
                result = self._translate_to_chinese(result)

            return result

        except JSONExtractionError as e:
            log.error("json_extraction_failed", error=str(e))
            return SummaryResult(
                executive_summary=[f"Error extracting JSON: {str(e)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=raw_text if 'raw_text' in locals() else str(e),
                validation_errors=[f"JSON extraction error: {str(e)}"],
            )
        except ValidationFailedError as e:
            log.error("validation_failed", errors=e.errors)
            return SummaryResult(
                executive_summary=[f"Validation failed: {', '.join(e.errors)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=raw_text if 'raw_text' in locals() else "",
                validation_errors=e.errors,
            )
        except httpx.HTTPError as e:
            latency_ms = (time.time() - start_time) * 1000
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
            log.error(
                "llm_http_error",
                error=str(e),
                latency_ms=round(latency_ms, 2),
                status_code=status_code,
            )
            return SummaryResult(
                executive_summary=[f"HTTP error: {str(e)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=str(e),
                validation_errors=[f"HTTP error: {str(e)}"],
            )
        except CircuitBreakerOpenError as e:
            latency_ms = (time.time() - start_time) * 1000
            log.error(
                "circuit_breaker_open",
                error=str(e),
                latency_ms=round(latency_ms, 2),
            )
            return SummaryResult(
                executive_summary=[
                    "LLM API is temporarily unavailable due to repeated failures. "
                    "The system has entered a protective mode and will retry automatically after a cooldown period."
                ],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=["Wait for LLM API recovery, then retry"],
                raw_response=str(e),
                validation_errors=["Circuit breaker is OPEN"],
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            log.error("summarize_failed", error=str(e), latency_ms=round(latency_ms, 2))
            return SummaryResult(
                executive_summary=[f"Error generating summary: {str(e)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=str(e),
                validation_errors=[f"Error: {str(e)}"],
            )

    def _translate_to_chinese(self, result: SummaryResult) -> SummaryResult:
        """Translate English summary result to Chinese using LLM."""
        log = self.logger.bind(operation="translate_to_chinese")
        log.debug("translation_started", sections_to_translate=3)

        # Load external prompt
        prompt = load_prompt(
            "translate_main",
            variables={
                "input_json": {
                    "executive_summary": result.executive_summary,
                    "themes": result.themes,
                    "action_items": result.action_items,
                },
            },
        )

        start_time = time.time()
        try:
            data = self._call_llm(prompt, max_tokens=4000)

            latency_ms = (time.time() - start_time) * 1000

            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
                log.warning("translation_empty_response")
                return result

            # Parse JSON from response
            parsed_data = self._extract_json_from_response(raw_text)
            translated = TranslationOutput.model_validate(parsed_data)

            # Translate top_updates individually to preserve structure
            log.debug("translating_top_updates", count=len(result.top_updates))
            translated_top_updates = []
            for update in result.top_updates:
                translated_update = self._translate_update_to_chinese(update)
                translated_top_updates.append(translated_update)

            # Translate release_notes individually
            log.debug("translating_release_notes", count=len(result.release_notes))
            translated_release_notes = []
            for note in result.release_notes:
                translated_note = self._translate_release_note_to_chinese(note)
                translated_release_notes.append(translated_note)

            log.info(
                "translation_success",
                latency_ms=round(latency_ms, 2),
                top_updates_translated=len(translated_top_updates),
                release_notes_translated=len(translated_release_notes),
            )

            return SummaryResult(
                executive_summary=translated.executive_summary or result.executive_summary,
                top_updates=translated_top_updates,
                release_notes=translated_release_notes,
                themes=translated.themes or result.themes,
                action_items=translated.action_items or result.action_items,
                raw_response=result.raw_response + "\n\n[Translated to Chinese]",
                validation_errors=result.validation_errors,
            )

        except (JSONExtractionError, ValidationError, Exception) as e:
            log.error("translation_failed", error=str(e), error_type=type(e).__name__)
            # If translation fails, return original result
            return result

    def _translate_update_to_chinese(self, update: dict) -> dict:
        """Translate a single top_update item to Chinese."""
        # Load external prompt
        prompt = load_prompt(
            "translate_update",
            variables={
                "input_json": {
                    "product": update.get("product", ""),
                    "title": update.get("title", ""),
                    "what_changed": update.get("what_changed", []),
                    "why_it_matters": update.get("why_it_matters", []),
                    "evidence": update.get("evidence", []),
                },
            },
        )

        try:
            data = self._call_llm(prompt, max_tokens=2000)

            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
                return update

            parsed_data = self._extract_json_from_response(raw_text)
            translated = TranslatedUpdate.model_validate(parsed_data)

            return {
                "product": update.get("product", ""),
                "title": translated.title or update.get("title", ""),
                "what_changed": translated.what_changed or update.get("what_changed", []),
                "why_it_matters": translated.why_it_matters or update.get("why_it_matters", []),
                "sources": update.get("sources", []),
                "evidence": translated.evidence or update.get("evidence", []),
            }
        except (JSONExtractionError, ValidationError, Exception):
            return update

    def _translate_release_note_to_chinese(self, note: dict) -> dict:
        """Translate a single release note item to Chinese."""
        # Load external prompt
        prompt = load_prompt(
            "translate_release",
            variables={
                "input_json": {
                    "product": note.get("product", ""),
                    "version": note.get("version", ""),
                    "highlights": note.get("highlights", []),
                },
            },
        )

        try:
            data = self._call_llm(prompt, max_tokens=1000)

            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
                return note

            parsed_data = self._extract_json_from_response(raw_text)
            translated = TranslatedReleaseNote.model_validate(parsed_data)

            return {
                "product": note.get("product", ""),
                "version": note.get("version", ""),
                "date": note.get("date", ""),
                "highlights": translated.highlights or note.get("highlights", []),
            }
        except (JSONExtractionError, ValidationError, Exception):
            return note


def summarize_items(items: List[RankedItem], top_k: int = 10, language: str = "en") -> SummaryResult:
    """Convenience function to summarize items."""
    summarizer = Summarizer(language=language)
    try:
        return summarizer.summarize(items, top_k=top_k)
    finally:
        # Close sync client
        summarizer.client.close()
        # Note: Async HTTP client is a singleton and should be closed
        # at application shutdown, not per-request
