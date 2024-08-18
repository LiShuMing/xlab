"""Base report generation tool - wraps existing researcher.py logic."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from ..types import ResearchMode, ResearchOptions, ResearchReport, ToolResult
from src.prompt_learner import (
    PROMPTS_OUTPUT_PATH,
    load_prompts,
    scan_and_learn,
    summarize_prompts,
)

if TYPE_CHECKING:
    pass

load_dotenv(Path.home() / ".env")
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
    """Get API key from environment."""
    key = os.environ.get("LLM_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("LLM_API_KEY environment variable is not set.")
    return key


def _get_refined_prompts(manifest: dict) -> str:
    """Get combined refined prompts from manifest."""
    prompts = manifest.get("prompts", [])
    if not prompts:
        return ""

    refined_prompts = []
    for p in prompts:
        text = p.get("refined_text") or p.get("normalized_text", "")
        if text:
            refined_prompts.append(
                f"<!-- Style from {p.get('source_file', 'unknown')} -->\n{text}"
            )

    return "\n\n".join(refined_prompts)


def _build_system_prompt(
    product_name: str,
    report_language: str,
    research_depth: str,
    prompts_path: Path = PROMPTS_OUTPUT_PATH,
) -> str:
    """Build the system prompt for the LLM."""
    manifest = load_prompts(prompts_path)
    if not manifest.get("prompts"):
        try:
            manifest = scan_and_learn(output_path=prompts_path)
        except Exception as exc:
            log.warning("prompt_learning_failed", error=str(exc))

    refined_prompts = _get_refined_prompts(manifest)

    if refined_prompts:
        log.info(
            "using_refined_prompts",
            char_count=len(refined_prompts),
            sources=len(manifest.get("prompts", [])),
        )
        learned_guide = f"""\
You MUST follow these detailed writing style guidelines extracted from reference documents:

{refined_prompts}

Additional structural requirements:"""
    else:
        learned_guide = summarize_prompts(manifest)

    return SYSTEM_PROMPT_TEMPLATE.format(
        product_name=product_name,
        learned_prompt_summary=learned_guide,
        report_language=report_language,
        research_depth=research_depth,
    )


class BaseReportTool:
    """Tool for generating the base research report."""

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self._client: AsyncAnthropic | None = None

    async def run(
        self,
        product_name: str,
        options: ResearchOptions,
    ) -> ToolResult:
        """Generate the base research report.

        Args:
            product_name: Name of the LLM API product to research.
            options: Research options including language and depth.

        Returns:
            ToolResult with ResearchReport data on success.
        """
        try:
            api_key = _get_api_key()
            base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
            model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)

            system_prompt = _build_system_prompt(
                product_name, options.language, options.depth
            )

            log.info(
                "calling_api",
                product=product_name,
                model=model,
                depth=options.depth,
                base_url=base_url,
            )

            async with AsyncAnthropic(
                api_key=api_key,
                base_url=base_url,
                timeout=self.timeout,
            ) as client:
                message = await client.messages.create(
                    model=model,
                    max_tokens=8192,
                    temperature=0.3,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Generate the full deep-research report for: {product_name}",
                        },
                    ],
                )

                # Handle different content block types
                content = ""
                for block in message.content:
                    if hasattr(block, "text"):
                        content = block.text
                        break

                if not content:
                    content_block = message.content[0]
                    if hasattr(content_block, "thinking"):
                        content = content_block.thinking
                    else:
                        content = str(content_block)

            log.info("report_generated", product=product_name, chars=len(content))

            report = ResearchReport.from_markdown(
                content, product_name, options.mode
            )
            return ToolResult.ok(data=report)

        except Exception as exc:
            log.error("base_report_failed", error=str(exc))
            return ToolResult.fail(str(exc))