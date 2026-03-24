"""Generate structured summaries using LLM API (OpenAI-compatible)."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from dbradar.config import get_config
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


class Summarizer:
    """Generate structured summaries using LLM."""

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
        Generate structured summary from ranked items.

        Args:
            items: List of ranked items.
            top_k: Number of top items to include in summary.

        Returns:
            SummaryResult with structured data.
        """
        if not items:
            return SummaryResult(
                executive_summary=["No updates found for the specified period."],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response="",
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
                )

            # Parse JSON from response
            # Handle potential markdown code block wrapper
            json_text = raw_text
            if "```json" in raw_text:
                json_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                json_text = raw_text.split("```")[1].split("```")[0]
            else:
                # Try to find JSON object
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_text = raw_text[start:end]

            parsed_data = json.loads(json_text.strip())

            result = SummaryResult(
                executive_summary=parsed_data.get("executive_summary", []),
                top_updates=parsed_data.get("top_updates", []),
                release_notes=parsed_data.get("release_notes", []),
                themes=parsed_data.get("themes", []),
                action_items=parsed_data.get("action_items", []),
                raw_response=raw_text,
            )

            # If Chinese is requested, translate the result
            if self.language == "zh":
                result = self._translate_to_chinese(result)

            return result

        except json.JSONDecodeError as e:
            return SummaryResult(
                executive_summary=["Error parsing summary response"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=f"JSON parse error: {str(e)}",
            )
        except Exception as e:
            return SummaryResult(
                executive_summary=[f"Error generating summary: {str(e)}"],
                top_updates=[],
                release_notes=[],
                themes=[],
                action_items=[],
                raw_response=str(e),
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
2. Keep technical terms accurate (e.g., "query optimizer" → "查询优化器", "lakehouse" → "湖仓一体")
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
            json_text = raw_text
            if "```json" in raw_text:
                json_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                json_text = raw_text.split("```")[1].split("```")[0]
            else:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_text = raw_text[start:end]

            translated = json.loads(json_text.strip())

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
                executive_summary=translated.get("executive_summary", result.executive_summary),
                top_updates=translated_top_updates,
                release_notes=translated_release_notes,
                themes=translated.get("themes", result.themes),
                action_items=translated.get("action_items", result.action_items),
                raw_response=result.raw_response + "\n\n[Translated to Chinese]",
            )

        except Exception:
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

            json_text = raw_text
            if "```json" in raw_text:
                json_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                json_text = raw_text.split("```")[1].split("```")[0]
            else:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_text = raw_text[start:end]

            translated = json.loads(json_text.strip())

            return {
                "product": update.get("product", ""),
                "title": translated.get("title", update.get("title", "")),
                "what_changed": translated.get("what_changed", update.get("what_changed", [])),
                "why_it_matters": translated.get("why_it_matters", update.get("why_it_matters", [])),
                "sources": update.get("sources", []),
                "evidence": translated.get("evidence", update.get("evidence", [])),
            }
        except Exception:
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

            json_text = raw_text
            if "```json" in raw_text:
                json_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                json_text = raw_text.split("```")[1].split("```")[0]
            else:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_text = raw_text[start:end]

            translated = json.loads(json_text.strip())

            return {
                "product": note.get("product", ""),
                "version": note.get("version", ""),
                "date": note.get("date", ""),
                "highlights": translated.get("highlights", note.get("highlights", [])),
            }
        except Exception:
            return note


def summarize_items(items: List[RankedItem], top_k: int = 10, language: str = "en") -> SummaryResult:
    """Convenience function to summarize items."""
    summarizer = Summarizer(language=language)
    try:
        return summarizer.summarize(items, top_k=top_k)
    finally:
        summarizer.client.close()
