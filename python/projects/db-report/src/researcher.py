"""Researcher: calls API using Anthropic SDK to generate deep research reports."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from anthropic import AsyncAnthropic, Anthropic
from dotenv import load_dotenv

from .exceptions import APIKeyMissingError, ResearcherError
from .prompt_learner import load_prompts, scan_and_learn, summarize_prompts, PROMPTS_OUTPUT_PATH
from .report_manager import save_report

load_dotenv(override=True)
log = structlog.get_logger()

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-max"

SYSTEM_PROMPT_TEMPLATE = """\
You are a senior AI product analyst specializing in large language model APIs and developer tooling.

Your task is to produce a comprehensive, structured deep-research report about the following LLM API product: {product_name}.

Follow these structural and stylistic guidelines learned from existing research documents:
{learned_prompt_summary}

The report MUST include the following sections:
1. Executive Summary (3–5 sentences)
2. Product Overview
   - Provider & background
   - Model family & versions
   - Core capabilities
3. Technical Deep Dive
   - Architecture & training approach (what is publicly known)
   - Context window, multimodal capabilities, tool use / function calling
   - Latency, throughput benchmarks (cite public sources where available)
4. API & Developer Experience
   - Authentication, SDKs, rate limits, pricing tiers
   - Ease of integration (REST, streaming, batch)
   - Playground / UI tooling
5. Competitive Positioning
   - Strengths vs. key competitors
   - Weaknesses / gaps
   - SWOT table (Markdown table format)
6. Use Case Analysis
   - Best-fit scenarios
   - Anti-patterns / poor-fit scenarios
7. Ecosystem & Community
   - Documentation quality
   - Community size, GitHub activity, third-party integrations
8. Pricing & Commercial Terms
   - Input/output token pricing
   - Fine-tuning, batch, cached token pricing
   - Enterprise / volume discounts
9. Recent Developments & Roadmap (last 6 months)
10. Analyst Verdict
    - Score (1–10) for: Capability / Dev Experience / Pricing / Ecosystem / Innovation
    - Final recommendation

Output the entire report in Markdown format. Use tables, code blocks, and callout blockquotes where appropriate.
Report language: {report_language}
Research depth: {research_depth}
"""


def _get_api_key() -> str:
    # Try ANTHROPIC_API_KEY first, then QWEN_API_KEY
    key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("QWEN_API_KEY", "")
    if not key:
        raise APIKeyMissingError("ANTHROPIC_API_KEY or QWEN_API_KEY environment variable is not set.")
    return key


def _get_refined_prompts(manifest: dict) -> str:
    """Get combined refined prompts from manifest."""
    prompts = manifest.get("prompts", [])
    if not prompts:
        return ""
    
    # Use refined_text if available, otherwise normalized_text
    refined_prompts = []
    for p in prompts:
        text = p.get("refined_text") or p.get("normalized_text", "")
        if text:
            refined_prompts.append(f"<!-- Style from {p.get('source_file', 'unknown')} -->\n{text}")
    
    return "\n\n".join(refined_prompts)


def _build_system_prompt(
    product_name: str,
    report_language: str,
    research_depth: str,
    prompts_path: Path = PROMPTS_OUTPUT_PATH,
) -> str:
    manifest = load_prompts(prompts_path)
    if not manifest.get("prompts"):
        # try to learn on-the-fly
        try:
            manifest = scan_and_learn(output_path=prompts_path)
        except Exception as exc:
            log.warning("prompt_learning_failed", error=str(exc))
    
    # Get refined prompts (full text, not summary)
    refined_prompts = _get_refined_prompts(manifest)
    
    if refined_prompts:
        # Use refined prompts as the primary writing guide
        log.info("using_refined_prompts", char_count=len(refined_prompts), sources=len(manifest.get("prompts", [])))
        learned_guide = f"""\
You MUST follow these detailed writing style guidelines extracted from reference documents:

{refined_prompts}

Additional structural requirements:"""
    else:
        # Fallback to summary
        learned_guide = summarize_prompts(manifest)
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        product_name=product_name,
        learned_prompt_summary=learned_guide,
        report_language=report_language,
        research_depth=research_depth,
    )


async def generate_report_async(
    product_name: str,
    report_language: str = "English",
    research_depth: str = "deep",
    prompts_path: Path = PROMPTS_OUTPUT_PATH,
    timeout: float = 120.0,
) -> str:
    """Call API using Anthropic SDK asynchronously and return the generated report as a string."""
    api_key = _get_api_key()
    base_url = os.environ.get("QWEN_BASE_URL", DEFAULT_BASE_URL)
    # Support both ANTHROPIC_MODEL and QWEN_MODEL env vars
    model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("QWEN_MODEL", DEFAULT_MODEL)

    system_prompt = _build_system_prompt(product_name, report_language, research_depth, prompts_path)

    log.info("calling_api", product=product_name, model=model, depth=research_depth, base_url=base_url)

    try:
        async with AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        ) as client:
            message = await client.messages.create(
                model=model,
                max_tokens=8192,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Generate the full deep-research report for: {product_name}"},
                ],
            )
            # Handle different content block types (find TextBlock)
            content = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    content = block.text
                    break
            if not content:
                # Fallback to first block
                content_block = message.content[0]
                if hasattr(content_block, 'thinking'):
                    content = content_block.thinking
                else:
                    content = str(content_block)
    except Exception as exc:
        raise ResearcherError(f"API request failed: {exc}") from exc

    log.info("report_generated", product=product_name, chars=len(content))
    return content


def generate_and_save(
    product_name: str,
    report_language: str = "English",
    research_depth: str = "deep",
    prompts_path: Path = PROMPTS_OUTPUT_PATH,
) -> Path:
    """Synchronous wrapper: generate and persist a report."""
    content = asyncio.run(generate_report_async(product_name, report_language, research_depth, prompts_path))
    return save_report(product_name, content)


if __name__ == "__main__":
    import sys
    product = sys.argv[1] if len(sys.argv) > 1 else "OpenAI GPT-4o"
    depth = sys.argv[2] if len(sys.argv) > 2 else "deep"
    path = generate_and_save(product, research_depth=depth)
    print(f"Report saved to {path}")
