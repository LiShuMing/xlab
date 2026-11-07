"""Shared test fixtures and configuration."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing config loading."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def sample_env_content():
    """Sample .env content for testing."""
    return """
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=sk-test-key-123
LLM_MODEL=test-model
LLM_MAX_CONCURRENT=8
LLM_TIMEOUT=60
LLM_MAX_TOKENS=2048
LLM_MODEL_1=model-a,https://a.example.com/v1,key-a
LLM_MODEL_2=model-b,https://b.example.com/v1,key-b
"""