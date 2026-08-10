"""Base report generation tool - wraps existing researcher.py logic."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import structlog
from dotenv import load_dotenv

from ..types import ResearchMode, ResearchOptions, ResearchReport, ToolResult
from src.prompt_learner import (
    PROMPTS_OUTPUT_PATH,
    load_prompts,
    scan_and_learn,
    summarize_prompts,
)

load_dotenv(Path.home() / ".env")
load_dotenv(override=True)

log = structlog.get_logger()

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-max"
DEFAULT_MAX_TOKENS = 8192

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


def _get_max_tokens() -> int:
    """Get maximum generated tokens for the base report call."""
    raw = os.environ.get("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))
    try:
        value = int(raw)
    except ValueError:
        log.warning("invalid_llm_max_tokens", value=raw, fallback=DEFAULT_MAX_TOKENS)
        return DEFAULT_MAX_TOKENS
    return max(1, value)


def _chat_completions_url(base_url: str) -> str:
    """Return the OpenAI-compatible chat completions endpoint."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _extract_chat_content(payload: dict) -> str:
    """Extract assistant content from an OpenAI-compatible response payload."""
    choices = payload.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)

    return ""


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
            max_tokens = _get_max_tokens()

            system_prompt = _build_system_prompt(
                product_name, options.language, options.depth
            )

            log.info(
                "calling_api",
                product=product_name,
                model=model,
                depth=options.depth,
                base_url=base_url,
                max_tokens=max_tokens,
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    _chat_completions_url(base_url),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": (
                                    "Generate the full deep-research report for: "
                                    f"{product_name}"
                                ),
                            },
                        ],
                    },
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(
                        f"LLM request failed with HTTP {response.status_code}: "
                        f"{response.text[:1000]}"
                    ) from exc
                content = _extract_chat_content(response.json())

            if not content:
                raise ValueError("LLM response did not include assistant content.")

            log.info("report_generated", product=product_name, chars=len(content))

            report = ResearchReport.from_markdown(
                content, product_name, options.mode
            )
            return ToolResult.ok(data=report)

        except Exception as exc:
            if isinstance(exc, httpx.TimeoutException):
                error = f"LLM request timed out after {self.timeout:.0f}s"
            else:
                error = str(exc) or exc.__class__.__name__
            log.error("base_report_failed", error=error)
            return ToolResult.fail(error)
