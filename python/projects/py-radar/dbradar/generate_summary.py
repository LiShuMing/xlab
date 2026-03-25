"""Generate summary for a single item - used by background task.

This module is designed to be run as a subprocess from the server
to generate summaries without blocking the main server process.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbradar.config import get_config
from dbradar.storage import DuckDBStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_summary_for_item(item_id: str) -> bool:
    """Generate a summary for a single item.

    Args:
        item_id: The unique ID of the item to summarize.

    Returns:
        True if successful, False otherwise.
    """
    config = get_config()

    # Initialize storage
    store = DuckDBStore(
        data_dir=config.output_dir.parent / "data",
        db_name="items.duckdb",
    )

    try:
        # Get the item
        item = store.get_by_id(item_id)
        if not item:
            logger.error(f"Item {item_id} not found")
            return False

        # Skip if already has summary
        if item.summary and item.summary.strip():
            logger.info(f"Item {item_id} already has summary, skipping")
            return True

        # Generate summary using LLM
        summary = _generate_summary_with_llm(item)

        if summary:
            # Update the item with the new summary
            success = store.update_summary(item_id, summary)
            if success:
                logger.info(f"Summary updated for item {item_id}")
                return True
            else:
                logger.error(f"Failed to update summary for item {item_id}")
                return False
        else:
            logger.error(f"Failed to generate summary for item {item_id}")
            return False

    finally:
        store.close()


def _generate_summary_with_llm(item) -> str | None:
    """Generate a summary for an item using LLM API.

    Args:
        item: The StorageItem to summarize.

    Returns:
        The generated summary string, or None if generation failed.
    """
    import httpx

    config = get_config()

    # Build prompt for single item summary
    prompt = f"""You are a technical content summarizer. Create a concise 2-3 sentence summary of the following article.

## Article Information

Title: {item.title or item.original_title}
Product: {item.product or 'Unknown'}
Content Type: {item.content_type or 'article'}
URL: {item.url}

## Raw Content

{item.raw_content[:3000] if item.raw_content else '[No raw content available]'}

## Instructions

1. Summarize the key points in 2-3 clear, concise sentences
2. Focus on what changed and why it matters
3. Use professional, technical language appropriate for database engineers
4. Do not include markdown formatting
5. Maximum 200 characters

Return only the summary text, nothing else."""

    try:
        client = httpx.Client(timeout=config.timeout)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }

        payload = {
            "model": config.model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = client.post(
            f"{config.base_url}/chat/completions",
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

        client.close()

        if raw_text:
            # Clean up the summary
            summary = raw_text.strip()
            # Remove quotes if present
            if summary.startswith('"') and summary.endswith('"'):
                summary = summary[1:-1]
            if summary.startswith("'") and summary.endswith("'"):
                summary = summary[1:-1]
            return summary

        return None

    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return None


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(description="Generate summary for a single item")
    parser.add_argument("--item-id", required=True, help="The ID of the item to summarize")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    success = generate_summary_for_item(args.item_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
