"""Utility functions for agents module."""

import json
import re
from typing import Optional

from core.llm import LLMClient, HumanMessage


def strip_markdown_fences(text: str) -> str:
    """Strip markdown JSON fences from text.

    Args:
        text: Text potentially wrapped in markdown fences.

    Returns:
        Text with markdown fences removed.
    """
    return re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL).strip()


async def parse_llm_json(
    text: str,
    llm_client: LLMClient,
    retry_prompt: Optional[str] = None
) -> dict:
    """Parse LLM output as JSON, stripping fences and retrying on parse error.

    Args:
        text: Raw LLM output text.
        llm_client: LLM client for retry on parse error.
        retry_prompt: Optional custom retry prompt.

    Returns:
        Parsed JSON dictionary, or empty dict on failure.
    """
    content = strip_markdown_fences(text)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Retry once
        if retry_prompt is None:
            retry_prompt = "Return ONLY the JSON object, no other text:"

        try:
            response = await llm_client.model.ainvoke([HumanMessage(content=retry_prompt)])
            content = strip_markdown_fences(response.content)
            return json.loads(content)
        except Exception:
            return {}


def format_relevant_data(
    data: dict,
    keys: list[str],
    max_chars: int = 3000
) -> str:
    """Format relevant data from collected data dict.

    Args:
        data: Full collected data dict.
        keys: Keys to extract and format.
        max_chars: Maximum character limit.

    Returns:
        Formatted string of relevant data.
    """
    result_parts = []

    for key in keys:
        if key in data:
            value = data[key]
            # Convert to string if needed
            if hasattr(value, 'content'):
                value_str = str(value.content) if value.content else ""
            else:
                value_str = str(value) if value else ""

            result_parts.append(f"{key}:\n{value_str}")

    result = "\n\n".join(result_parts)

    # Truncate if needed
    if len(result) > max_chars:
        result = result[:max_chars] + "...[truncated]"

    return result