"""Generate structured summaries using LLM API (OpenAI-compatible).

This module implements structured output validation using Pydantic models
as per Harness Engineering standards (see RULE.md).
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from pydantic import ValidationError

from dbradar.config import get_config
from dbradar.models import (
    SummaryOutput,
    TranslationOutput,
    TranslatedUpdate,
    TranslatedReleaseNote,
)
from dbradar.ranker import RankedItem

DEFAULT_MODEL = "qwen3.5-plus"


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
        self.client = httpx.Client(timeout=self.timeout)

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
        """Build the summarization prompt."""
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

        # Always use English for generation, translation will be done separately if needed
        role_desc = "You are a senior database engineer analyzing industry updates for DB/OLAP systems"
        task_desc = "Analyze the following collected items and produce a structured daily radar report"
        output_format_title = "Output Format"
        rules_title = "Rules"
        lang_instruction = "**Important: Write all content in English.**"
        current_date_title = "Current Date"
        return_instruction = "Return ONLY the JSON object, no additional text or markdown formatting."
        focus_areas = "performance, execution engine, storage, query optimizer, governance, cost, serverless, lakehouse"
        executive_summary_desc = "Executive summary: 5 bullets max, high-level overview"
        action_items_desc = "Action items should be concrete (e.g., \"check feature X\", \"benchmark idea Y\")"
        themes_desc = "Themes should reflect broader industry trends"
        not_invent_facts = "**DO NOT invent facts** - Only use information present in the snippets"
        evidence_limit = "Evidence snippets should be <= 40 words each"
        what_changed_desc = 'For "what_changed", extract 2-4 concrete changes from the content'
        why_matters_desc = 'For "why_it_matters", explain relevance to OLAP/query engines (2 bullets)'

        prompt = f"""{role_desc}.

## {task_desc}

{lang_instruction}

## Input Data
You have {len(item_data)} items to analyze. Here is the data:

{json.dumps(item_data, indent=2, ensure_ascii=False)}

## {output_format_title}
Generate a JSON object with the following structure (NO markdown code blocks, just raw JSON):

{{
    "executive_summary": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
    "top_updates": [
        {{
            "product": "ProductName",
            "title": "Title of the update",
            "what_changed": ["change 1", "change 2", "change 3"],
            "why_it_matters": ["reason 1", "reason 2"],
            "sources": ["url1"],
            "evidence": ["snippet1", "snippet2"]
        }}
    ],
    "release_notes": [
        {{
            "product": "ProductName",
            "version": "version info if available",
            "date": "release date",
            "highlights": ["highlight 1", "highlight 2"]
        }}
    ],
    "themes": ["theme 1", "theme 2", "theme 3", "theme 4"],
    "action_items": ["action 1", "action 2", "action 3", "action 4", "action 5"]
}}

## {rules_title}
1. {not_invent_facts}
2. Include URLs as sources for every claim
3. {evidence_limit}
4. {what_changed_desc}
5. {why_matters_desc}
6. Focus on: {focus_areas}
7. {executive_summary_desc}
8. {action_items_desc}
9. {themes_desc}
10. **IMPORTANT**: Include ALL meaningful updates in top_updates, not just the most important ones. Aim for comprehensive coverage. Include updates even if they seem minor but are from key products.

## {current_date_title}
{datetime.now(timezone.utc).strftime("%Y-%m-%d")}

{return_instruction}
"""
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
        if not items:
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

        try:
            # Build OpenAI-compatible API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Extract response text
            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
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

            # If Chinese is requested, translate the result
            if self.language == "zh":
                result = self._translate_to_chinese(result)

            return result

        except JSONExtractionError as e:
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
            return SummaryResult(
                executive_summary=[f"Validation failed: {', '.join(e.errors)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=raw_text if 'raw_text' in locals() else "",
                validation_errors=e.errors,
            )
        except Exception as e:
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
        prompt = f"""You are a professional translator specializing in technical content translation from English to Chinese (Simplified).

## Task
Translate the following JSON content from English to Chinese. Keep the JSON structure exactly the same, only translate the text values.

## Input JSON
{json.dumps({
    "executive_summary": result.executive_summary,
    "themes": result.themes,
    "action_items": result.action_items,
}, indent=2, ensure_ascii=False)}

## Translation Rules
1. Translate all text content to natural, fluent Simplified Chinese
2. Keep technical terms accurate (e.g., "query optimizer" -> "查询优化器", "lakehouse" -> "湖仓一体")
3. Maintain professional database/OLAP industry terminology
4. Keep product names, version numbers, and URLs unchanged
5. Do not add or remove any fields

## Output Format
Return ONLY the JSON object with the same structure, no markdown code blocks:
{{
    "executive_summary": ["翻译后的要点1", "翻译后的要点2", ...],
    "themes": ["主题1", "主题2", ...],
    "action_items": ["行动项1", "行动项2", ...]
}}
"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    raw_text = choice["message"]["content"]

            if not raw_text:
                return result

            # Parse JSON from response
            parsed_data = self._extract_json_from_response(raw_text)
            translated = TranslationOutput.model_validate(parsed_data)

            # Translate top_updates individually to preserve structure
            translated_top_updates = []
            for update in result.top_updates:
                translated_update = self._translate_update_to_chinese(update)
                translated_top_updates.append(translated_update)

            # Translate release_notes individually
            translated_release_notes = []
            for note in result.release_notes:
                translated_note = self._translate_release_note_to_chinese(note)
                translated_release_notes.append(translated_note)

            return SummaryResult(
                executive_summary=translated.executive_summary or result.executive_summary,
                top_updates=translated_top_updates,
                release_notes=translated_release_notes,
                themes=translated.themes or result.themes,
                action_items=translated.action_items or result.action_items,
                raw_response=result.raw_response + "\n\n[Translated to Chinese]",
                validation_errors=result.validation_errors,
            )

        except (JSONExtractionError, ValidationError, Exception):
            # If translation fails, return original result
            return result

    def _translate_update_to_chinese(self, update: dict) -> dict:
        """Translate a single top_update item to Chinese."""
        prompt = f"""Translate the following JSON content from English to Chinese (Simplified). Keep the JSON structure and keep product names, URLs unchanged.

Input:
{json.dumps({
    "product": update.get("product", ""),
    "title": update.get("title", ""),
    "what_changed": update.get("what_changed", []),
    "why_it_matters": update.get("why_it_matters", []),
    "evidence": update.get("evidence", []),
}, indent=2, ensure_ascii=False)}

Return ONLY the JSON object, no markdown:
{{
    "product": "keep original",
    "title": "translated title",
    "what_changed": ["翻译1", "翻译2"],
    "why_it_matters": ["翻译1", "翻译2"],
    "evidence": ["keep original or translate if natural"]
}}"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

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
        prompt = f"""Translate the following JSON content from English to Chinese (Simplified). Keep product names and version numbers unchanged.

Input:
{json.dumps({
    "product": note.get("product", ""),
    "version": note.get("version", ""),
    "highlights": note.get("highlights", []),
}, indent=2, ensure_ascii=False)}

Return ONLY the JSON object:
{{
    "product": "keep original",
    "version": "keep original",
    "highlights": ["翻译1", "翻译2"]
}}"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

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
        summarizer.client.close()
