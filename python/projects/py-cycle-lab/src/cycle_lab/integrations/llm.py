"""Minimal OpenAI-compatible LLM integration using the standard library."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from cycle_lab.config import load_local_env


def _chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def generate_market_brief(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a short research brief from dashboard state.

    Returns a structured response and never raises provider errors to callers.
    """

    load_local_env()
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    timeout = int(os.getenv("LLM_TIMEOUT", "30"))

    if not (base_url and api_key and model):
        return {
            "ok": False,
            "error": "LLM is not fully configured. Expected LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.",
        }

    system = (
        "You are a cautious long-term investment research assistant. "
        "Summarize market state without giving buy/sell advice. "
        "Use action states like observe, pause adding, review thesis, or rebalance review."
    )
    user = (
        "Create a concise Chinese market-state brief from this dashboard payload. "
        "Include: cycle state, valuation state, main risks, and watchlist discipline. "
        f"Payload JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }

    request = urllib.request.Request(
        _chat_url(base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"LLM HTTP error: {exc.code}"}
    except Exception as exc:  # pragma: no cover - network boundary
        return {"ok": False, "error": f"LLM request failed: {type(exc).__name__}"}

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        return {"ok": False, "error": "LLM response did not include choices[0].message.content."}

    return {"ok": True, "content": content}
