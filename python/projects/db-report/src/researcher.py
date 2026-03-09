"""Researcher: calls Qwen API to generate deep research reports on LLM API products."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import structlog
from dotenv import load_dotenv

from .exceptions import APIKeyMissingError, ResearcherError
from .prompt_learner import load_prompts, scan_and_learn, summarize_prompts, PROMPTS_OUTPUT_PATH
from .report_manager import save_report

load_dotenv()
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
    key = os.environ.get("QWEN_API_KEY", "")
    if not key:
        raise APIKeyMissingError("QWEN_API_KEY environment variable is not set.")
    return key


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
    summary = summarize_prompts(manifest)
    return SYSTEM_PROMPT_TEMPLATE.format(
        product_name=product_name,
        learned_prompt_summary=summary,
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
    """Call Qwen API asynchronously and return the generated report as a string."""
    api_key = _get_api_key()
    base_url = os.environ.get("QWEN_BASE_URL", DEFAULT_BASE_URL)
    model = os.environ.get("QWEN_MODEL", DEFAULT_MODEL)

    system_prompt = _build_system_prompt(product_name, report_language, research_depth, prompts_path)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the full deep-research report for: {product_name}"},
        ],
        "temperature": 0.3,
        "max_tokens": 8192,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    log.info("calling_api", product=product_name, model=model, depth=research_depth)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise ResearcherError(f"API returned {exc.response.status_code}: {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise ResearcherError(f"API request failed: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ResearcherError(f"Unexpected API response structure: {data}") from exc

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
