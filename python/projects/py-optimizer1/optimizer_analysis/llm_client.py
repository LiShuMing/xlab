"""LLM client for AI-powered optimizer analysis."""
import time
from typing import Optional, List
import httpx
from pydantic import BaseModel

from optimizer_analysis.config import LLMConfig


class ChatMessage(BaseModel):
    """Chat message structure."""
    role: str
    content: str


class LLMClient:
    """OpenAI-compatible LLM client for analysis tasks."""

    def __init__(self, config: LLMConfig, max_retries: int = 3):
        self.config = config
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }
        )

    def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Send chat completion request with retry logic."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.post(
                    "/chat/completions",
                    json={
                        "model": self.config.model,
                        "messages": [m.model_dump() for m in messages],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # exponential backoff
                    time.sleep(wait_time)
                continue
        raise last_error if last_error else RuntimeError("Unknown error")

    def analyze_code(
        self,
        code: str,
        question: str,
        context: Optional[str] = None,
    ) -> str:
        """Analyze code with a specific question."""
        system_prompt = """You are an expert in database query optimizers.
Analyze the provided code and answer questions about optimizer architecture,
rules, cost models, and implementation patterns.
Be precise and reference specific code sections when relevant."""

        user_content = f"Code:\n```\n{code}\n```\n\nQuestion: {question}"
        if context:
            user_content = f"Context: {context}\n\n{user_content}"

        return self.chat([
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ])

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Create LLM client from config or environment."""
    if config is None:
        config = LLMConfig.from_env_file()
    return LLMClient(config)