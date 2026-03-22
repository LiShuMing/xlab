"""BM25-based chunk retrieval for QA."""

from __future__ import annotations

import re
from typing import Any


def retrieve_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 6,
    skip_references: bool = True,
) -> list[dict[str, Any]]:
    """
    Retrieve top-k relevant chunks using BM25 scoring.

    Falls back to simple TF scoring if rank_bm25 is not installed.
    Filters out reference sections by default.
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
        return [c for _, c in ranked[:top_k]]
    except ImportError:
        # Fallback: simple keyword overlap
        query_tokens = set(_tokenize(query))
        scored = []
        for c in candidates:
            chunk_tokens = set(_tokenize(c["text"]))
            overlap = len(query_tokens & chunk_tokens)
            scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenization."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens
