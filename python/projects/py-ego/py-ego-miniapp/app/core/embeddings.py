"""Async embedding generation with fallback strategies.

This module provides async embedding generation using sentence-transformers
with automatic fallback to hash-based embeddings on errors.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.config import get_settings

logger = logging.getLogger(__name__)

# Suppress verbose logging from ML libraries
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

# Module-level cache for the embedder
_local_embedder: Any | None = None


def _simple_hash_embedding(text: str, dim: int = 512) -> NDArray[np.float32]:
    """Generate deterministic hash-based embedding vector.

    This is used as a fallback when the embedding model fails.
    It produces consistent vectors for the same text.

    Args:
        text: Input text to embed.
        dim: Dimension of the output vector.

    Returns:
        NDArray[np.float32]: Normalized random vector derived from text hash.
    """
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def _get_local_embedder() -> Any:
    """Get or create the local embedding model (lazy loaded).

    Returns:
        The SentenceTransformer model instance.
    """
    global _local_embedder
    if _local_embedder is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _local_embedder = SentenceTransformer(settings.embedding_model, device="cpu")
        logger.info("Embedding model loaded successfully")
    return _local_embedder


def _clean_text(text: str) -> str:
    """Clean text by removing invalid characters.

    Args:
        text: Raw input text.

    Returns:
        str: Cleaned text safe for embedding.
    """
    if not text:
        return ""
    # Remove surrogate pairs and control characters
    text = text.encode("utf-8", "ignore").decode("utf-8")
    text = "".join(
        char for char in text
        if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF)
    )
    return text.strip()


async def get_embedding(text: str) -> NDArray[np.float32]:
    """Get embedding vector for a single text.

    Runs the embedding model in a thread pool to avoid blocking
    the event loop. Falls back to hash embedding on errors.

    Args:
        text: Input text to embed.

    Returns:
        NDArray[np.float32]: The embedding vector (normalized).
    """
    cleaned = _clean_text(text)
    if not cleaned:
        cleaned = ""

    settings = get_settings()

    try:
        embedder = _get_local_embedder()
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: embedder.encode(
                cleaned,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
        )
        return embedding.astype(np.float32)
    except Exception as e:
        logger.warning(f"Embedding failed, using hash fallback: {e}")
        return _simple_hash_embedding(cleaned, settings.embedding_dimension)


async def get_embeddings_batch(texts: list[str]) -> list[NDArray[np.float32]]:
    """Get embedding vectors for multiple texts efficiently.

    Processes texts in a single batch for better performance.
    Falls back to individual hash embeddings on errors.

    Args:
        texts: List of input texts to embed.

    Returns:
        list[NDArray[np.float32]]: List of embedding vectors.
    """
    if not texts:
        return []

    settings = get_settings()
    cleaned = [_clean_text(t) for t in texts]

    try:
        embedder = _get_local_embedder()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: embedder.encode(
                cleaned,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
        )
        return [e.astype(np.float32) for e in embeddings]
    except Exception as e:
        logger.warning(f"Batch embedding failed, using hash fallback: {e}")
        return [
            _simple_hash_embedding(t, settings.embedding_dimension) for t in cleaned
        ]
