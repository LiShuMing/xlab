"""BM25-based chunk retrieval for QA."""

from __future__ import annotations

import re
from typing import Any

from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)


def retrieve_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 6,
    skip_references: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve top-k relevant chunks using BM25 scoring.

    Falls back to simple TF scoring if rank_bm25 is not installed.
    Filters out reference sections by default.

    Args:
        query: Search query
        chunks: Available chunks
        top_k: Number of chunks to return
        skip_references: Whether to filter out reference sections

    Returns:
        List of top-k most relevant chunks
    """
    if skip_references:
        candidates = [
            c for c in chunks
            if "reference" not in c.get("section_normalized", "").lower()
        ]
    else:
        candidates = chunks

    if not candidates:
        return []

    try:
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [_tokenize(c["text"]) for c in candidates]
        bm25 = BM25Okapi(tokenized_corpus)
        query_tokens = _tokenize(query)
        scores = bm25.get_scores(query_tokens)
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        logger.debug(
            "bm25_retrieval",
            query=query[:50],
            candidates=len(candidates),
            top_k=top_k,
        )
        return [c for _, c in ranked[:top_k]]
    except ImportError:
        # Fallback: simple keyword overlap
        logger.debug(
            "fallback_retrieval",
            query=query[:50],
            candidates=len(candidates),
            reason="rank_bm25_not_installed",
        )
        query_tokens = _tokenize(query)
        scored: list[tuple[int, dict[str, Any]]] = []
        for c in candidates:
            chunk_tokens = _tokenize(c["text"])
            overlap = _count_overlap(query_tokens, chunk_tokens)
            scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenization.

    Args:
        text: Text to tokenize

    Returns:
        List of lowercase alphanumeric tokens
    """
    text = text.lower()
    tokens: list[str] = re.findall(r"[a-z0-9]+", text)
    return tokens


def _count_overlap(list1: list[str], list2: list[str]) -> int:
    """Count overlapping elements between two lists.

    Args:
        list1: First list
        list2: Second list

    Returns:
        Number of common elements
    """
    set1 = set(list1)
    set2 = set(list2)
    return len(set1 & set2)
