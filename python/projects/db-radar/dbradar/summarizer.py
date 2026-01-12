"""Generate structured summaries using Anthropic."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from anthropic import Anthropic

from dbradar.config import get_config
from dbradar.ranker import RankedItem


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

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        config = get_config()
        self.client = Anthropic(
            api_key=api_key or config.api_key,
            base_url=base_url or config.base_url,
        )
        self.model = "claude-sonnet-4-20250514"

    def _build_prompt(self, items: List[RankedItem], top_k: int = 10) -> str:
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

        prompt = f"""You are a senior database engineer analyzing industry updates for DB/OLAP systems.

## Task
Analyze the following collected items and produce a structured daily radar report.

## Input Data
You have {len(item_data)} items to analyze. Here is the data:

{item_data}

## Output Format
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

## Rules
1. **DO NOT invent facts** - Only use information present in the snippets
2. Include URLs as sources for every claim
3. Evidence snippets should be <= 40 words each
4. For "what_changed", extract 2-4 concrete changes from the content
5. For "why_it_matters", explain relevance to OLAP/query engines (2 bullets)
6. Focus on: performance, execution engine, storage, query optimizer, governance, cost, serverless, lakehouse
7. Executive summary: 5 bullets max, high-level overview
8. Action items should be concrete (e.g., "check feature X", "benchmark idea Y")
9. Themes should reflect broader industry trends

## Current Date
{datetime.now(timezone.utc).strftime("%Y-%m-%d")}

Return ONLY the JSON object, no additional text or markdown formatting.
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
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            # Handle different response block types
            raw_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_text = block.text
                    break
                elif hasattr(block, 'type') and block.type == 'text':
                    raw_text = block.text
                    break

            if not raw_text:
                return SummaryResult(
                    executive_summary=["Error: Empty response from API"],
                    top_updates=[],
                    release_notes=[],
                    themes=[],
                    action_items=[],
                    raw_response="",
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

            data = json.loads(json_text.strip())

            return SummaryResult(
                executive_summary=data.get("executive_summary", []),
                top_updates=data.get("top_updates", []),
                release_notes=data.get("release_notes", []),
                themes=data.get("themes", []),
                action_items=data.get("action_items", []),
                raw_response=raw_text,
            )

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


def summarize_items(items: List[RankedItem], top_k: int = 10) -> SummaryResult:
    """Convenience function to summarize items."""
    summarizer = Summarizer()
    return summarizer.summarize(items, top_k=top_k)
