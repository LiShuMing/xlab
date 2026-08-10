"""Generate a summary for one Radar item in the business database."""

from __future__ import annotations

import argparse
import asyncio
import logging

from backend._shared.llm import ChatMessage, LLMRuntimeConfig, SyncLLMClient
from backend._shared.logging import configure_logging
from backend._shared.storage import business_uow
from backend.radar.config import get_config
from backend.radar.db_models import RadarItem
from backend.settings import get_settings

configure_logging(get_settings())
logger = logging.getLogger(__name__)


def generate_summary_for_item(item_id: str) -> bool:
    """Generate and persist a summary for a single Radar item."""
    return asyncio.run(_generate_summary_for_item(item_id))


async def _generate_summary_for_item(item_id: str) -> bool:
    async with business_uow() as session:
        item = await session.get(RadarItem, item_id)
        if not item:
            logger.error("Item %s not found", item_id)
            return False

        if item.summary and item.summary.strip():
            logger.info("Item %s already has summary, skipping", item_id)
            return True

        summary = _generate_summary_with_llm(item)
        if not summary:
            logger.error("Failed to generate summary for item %s", item_id)
            return False

        item.summary = summary
        session.add(item)
        await session.flush()
        logger.info("Summary updated for item %s", item_id)
        return True


def _generate_summary_with_llm(item: RadarItem) -> str | None:
    config = get_config()

    prompt = f"""You are a technical content summarizer. Create a concise 2-3 sentence summary of the following article.

## Article Information

Title: {item.title or item.original_title}
Product: {item.product or "Unknown"}
Content Type: {item.content_type or "article"}
URL: {item.url}

## Raw Content

{item.raw_content[:3000] if item.raw_content else "[No raw content available]"}

## Instructions

1. Summarize the key points in 2-3 clear, concise sentences
2. Focus on what changed and why it matters
3. Use professional, technical language appropriate for database engineers
4. Do not include markdown formatting
5. Maximum 200 characters

Return only the summary text, nothing else."""

    try:
        client = SyncLLMClient(
            LLMRuntimeConfig(
                api_key=config.api_key or "",
                base_url=config.base_url or "https://api.openai.com/v1",
                model=config.model,
                timeout=config.timeout,
                max_retries=2,
            )
        )
        try:
            response = client.complete(
                [ChatMessage(role="user", content=prompt)],
                model=config.model,
                max_tokens=300,
            )
            raw_text = response.text
        finally:
            client.close()

        if not raw_text:
            return None

        summary = raw_text.strip()
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]
        if summary.startswith("'") and summary.endswith("'"):
            summary = summary[1:-1]
        return summary
    except Exception as exc:
        logger.error("LLM API error: %s", exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate summary for a single Radar item")
    parser.add_argument("--item-id", required=True, help="The Radar item ID to summarize")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    raise SystemExit(0 if generate_summary_for_item(args.item_id) else 1)


if __name__ == "__main__":
    main()
