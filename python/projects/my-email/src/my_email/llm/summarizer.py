"""
LLM summarization module.

Uses an OpenAI-compatible client, so it works with:
- Ollama (default): LLM_BASE_URL=http://localhost:11434/v1, LLM_API_KEY=ollama
- OpenAI:           LLM_BASE_URL=https://api.openai.com/v1,  LLM_API_KEY=sk-...
- Any other OpenAI-compatible endpoint (vLLM, LMStudio, etc.)

Output contract: EmailSummary is a Pydantic model. The model is asked to return
pure JSON; we strip markdown fences defensively in case the model disobeys.
"""

import json
import re

import structlog
from openai import OpenAI
from pydantic import BaseModel, Field

from my_email.config import settings

log = structlog.get_logger()


# ── output schema ─────────────────────────────────────────────────────────────

class EmailSummary(BaseModel):
    title: str = Field(description="Clean title of the email or newsletter issue")
    sender_org: str = Field(description="Organization or project name, e.g. 'Apache Iceberg'")
    topics: list[str] = Field(description="3–8 main technical topic keywords")
    summary: str = Field(description="2–4 sentence factual summary of the content")
    key_points: list[str] = Field(description="3–6 concrete bullet points worth remembering")
    relevance: str = Field(description='"high" | "medium" | "low" — for data/infra engineering')


# ── prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a technical digest assistant for a senior data/infrastructure engineer.
Read the email below and extract structured information.
Be precise and factual. Focus on technical content — ignore marketing, unsubscribe links, and boilerplate.
Return ONLY valid JSON. No markdown fences. No explanation."""

_USER_TEMPLATE = """\
Subject: {subject}
From: {sender}
Date: {date}

Body:
{body}

Return a JSON object with exactly these fields:
- title        (string) clean title
- sender_org   (string) organization or project name
- topics       (array of strings) 3–8 technical keywords
- summary      (string) 2–4 sentence factual summary
- key_points   (array of strings) 3–6 concrete points worth noting
- relevance    (string) "high" | "medium" | "low" — relevance to data engineering / distributed systems

JSON only."""


# ── client ────────────────────────────────────────────────────────────────────

def _build_client() -> OpenAI:
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers if the model adds them despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


# ── public API ────────────────────────────────────────────────────────────────

def summarize_message(subject: str, sender: str, date: str, body: str) -> EmailSummary:
    """
    Call the configured LLM and return a structured EmailSummary.

    Raises:
        json.JSONDecodeError  — if model returns non-parseable output
        pydantic.ValidationError — if JSON is valid but missing required fields
        openai.APIError       — on LLM API failure
    """
    client = _build_client()
    prompt = _USER_TEMPLATE.format(
        subject=subject, sender=sender, date=date, body=body
    )

    log.info("llm.summarize.start", model=settings.llm_model, subject=subject[:80])

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )

    raw = response.choices[0].message.content or ""
    raw = _strip_fences(raw)

    parsed = json.loads(raw)
    result = EmailSummary(**parsed)

    log.info(
        "llm.summarize.done",
        title=result.title[:60],
        relevance=result.relevance,
        topics=result.topics,
    )
    return result
