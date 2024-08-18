"""Embedding generation module with structured logging and error handling."""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import numpy as np
from numpy.typing import NDArray

from config import get_settings

# Configure environment before importing ML libraries
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# Suppress third-party library logs
for _name in [
    "sentence_transformers", "transformers", "urllib3", "httpcore",
    "openai", "huggingface_hub", "httpx", "tqdm", "torch",
]:
    logging.getLogger(_name).setLevel(logging.ERROR)
    logging.getLogger(_name).disabled = True

_local_embedder: Any = None

__all__ = ["get_embedding", "get_embeddings_batch", "clean_text"]


def clean_text(text: Any) -> str:
    """Clean text by removing surrogate characters and control characters."""
    if text is None:
        return ""
    text = str(text)
    text = text.encode("utf-8", "ignore").decode("utf-8")
    text = "".join(
        char for char in text
        if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF)
    )
    return text.strip() if text.strip() else ""


def _is_simple_embedding_mode() -> bool:
    """Check if we should use simple hash embeddings."""
    return os.getenv("USE_SIMPLE_EMBEDDING", "false").lower() == "true"


def _get_local_embedder() -> Any:
    """Get the local embedding model (lazy loaded)."""
    global _local_embedder
    if _local_embedder is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        _local_embedder = SentenceTransformer(settings.embedding_model, device="cpu")
    return _local_embedder


def _simple_hash_embedding(text: str, dim: int = 512) -> NDArray[np.float32]:
    """Generate a deterministic hash-based embedding vector (for testing)."""
    cleaned = clean_text(text)
    seed = int(hashlib.md5(cleaned.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def get_embedding(text: str) -> NDArray[np.float32]:
    """Get embedding vector for a single text."""
    cleaned = clean_text(text)

    # Always use simple embedding if explicitly requested
    if _is_simple_embedding_mode():
        return _simple_hash_embedding(cleaned)

    settings = get_settings()

    try:
        if settings.use_local_embedding:
            try:
                embedder = _get_local_embedder()
                embedding = embedder.encode(
                    cleaned,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return embedding.astype(np.float32)
            except ImportError:
                return _simple_hash_embedding(cleaned)
            except Exception as e:
                logging.error(f"Local embedding error: {e}")
                return _simple_hash_embedding(cleaned)
        else:
            from config import get_openai_client
            client = get_openai_client()
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=cleaned,
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
        logging.error(f"Embedding error: {e}")
        return _simple_hash_embedding(cleaned)


def get_embeddings_batch(texts: list[str], batch_size: int = 32) -> list[NDArray[np.float32]]:
    """Get embedding vectors for multiple texts efficiently."""
    if not texts:
        return []

    cleaned_texts = [clean_text(t) for t in texts]

    if _is_simple_embedding_mode():
        return [_simple_hash_embedding(t) for t in cleaned_texts]

    settings = get_settings()

    try:
        if settings.use_local_embedding:
            try:
                embedder = _get_local_embedder()
                embeddings = embedder.encode(
                    cleaned_texts,
                    convert_to_numpy=True,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
                return [e.astype(np.float32) for e in embeddings]
            except ImportError:
                return [_simple_hash_embedding(t) for t in cleaned_texts]
            except Exception as e:
                logging.error(f"Batch embedding error: {e}")
                return [_simple_hash_embedding(t) for t in cleaned_texts]
        else:
            from config import get_openai_client
            client = get_openai_client()
            response = client.embeddings.create(
                model=settings.embedding_model,
                input=cleaned_texts,
            )
            return [np.array(d.embedding, dtype=np.float32) for d in response.data]
    except Exception as e:
        logging.error(f"Batch embedding error: {e}")
        return [_simple_hash_embedding(t) for t in cleaned_texts]