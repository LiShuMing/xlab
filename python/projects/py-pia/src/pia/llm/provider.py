"""LLM provider abstraction.

Auto-detects the protocol from LLM_BASE_URL:
  - URL contains "anthropic" → use Anthropic Messages API (anthropic SDK)
  - Otherwise              → use OpenAI-compatible Chat API (openai SDK)

This lets pia work with:
  - Anthropic Claude directly (api.anthropic.com)
  - DashScope Anthropic-compatible proxy (coding.dashscope.aliyuncs.com/apps/anthropic)
  - Kimi / OpenAI / any OpenAI-compatible endpoint
"""

from __future__ import annotations

import json
import re
import structlog
from typing import TYPE_CHECKING

from pia.config.settings import get_settings
from pia.llm.schemas import ReleaseExtraction
from pia.llm.prompts import SYSTEM_PROMPT, make_extraction_prompt, make_analysis_prompt

if TYPE_CHECKING:
    from pia.models.product import Product
    from pia.models.release import Release
    from pia.models.source_doc import NormalizedDoc

log = structlog.get_logger()

PROMPT_VERSION = "v1"


def _is_anthropic_endpoint(base_url: str) -> bool:
    return "anthropic" in base_url.lower()


class LLMProvider:
    """LLM provider that auto-selects Anthropic or OpenAI SDK based on base_url."""

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self._base_url = settings.llm_base_url
        self._api_key = settings.llm_api_key
        self._timeout = settings.llm_timeout
        self._use_anthropic = _is_anthropic_endpoint(self._base_url)

        if self._use_anthropic:
            import anthropic
            self._client = anthropic.Anthropic(
                base_url=self._base_url,
                api_key=self._api_key,
            )
            log.info("llm backend: anthropic-compatible", base_url=self._base_url, model=self.model)
        else:
            import openai
            self._client = openai.OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=self._timeout,
            )
            log.info("llm backend: openai-compatible", base_url=self._base_url, model=self.model)

    def _call(self, messages: list[dict], max_tokens: int = 4096) -> str:
        """Synchronous call. Handles both Anthropic and OpenAI protocols."""
        log.info("llm call", model=self.model, max_tokens=max_tokens)

        if self._use_anthropic:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            if not text_blocks:
                raise ValueError(f"Empty Anthropic response: {response}")
            return "\n".join(text_blocks)
        else:
            full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
            response = self._client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError(f"Empty OpenAI response: {response}")
            return content

    async def extract_release_info(
        self,
        product_name: str,
        version: str,
        content: str,
    ) -> ReleaseExtraction:
        """Stage A: structured extraction from release notes."""
        prompt = make_extraction_prompt(product_name, version, content)
        text = self._call([{"role": "user", "content": prompt}], max_tokens=4096)

        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                log.error("no json in extraction response", preview=text[:500])
                raise ValueError("LLM did not return valid JSON in extraction response")

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            log.error("json parse error", error=str(e), preview=json_text[:500])
            raise ValueError(f"Failed to parse LLM JSON: {e}") from e

        return ReleaseExtraction.model_validate(data)

    async def generate_analysis(
        self,
        product: "Product",
        release: "Release",
        extraction: ReleaseExtraction,
        normalized_doc: "NormalizedDoc",
        supplemental: list[str] | None = None,
    ) -> tuple[str, str]:
        """Stage B: generate full expert analysis report."""
        prompt = make_analysis_prompt(product, release, extraction, normalized_doc, supplemental)
        content = self._call([{"role": "user", "content": prompt}], max_tokens=8192)
        return content, PROMPT_VERSION

    async def generate_digest(
        self,
        products_info: list[dict],
        time_window: str,
    ) -> tuple[str, str]:
        """Generate a multi-product digest report."""
        from pia.llm.prompts import make_digest_prompt
        prompt = make_digest_prompt(products_info, time_window)
        content = self._call([{"role": "user", "content": prompt}], max_tokens=8192)
        return content, PROMPT_VERSION
