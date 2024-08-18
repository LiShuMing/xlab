"""FAISS-based memory storage with type-safe operations."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from numpy.typing import NDArray

from embeddings import get_embedding, get_embeddings_batch
from exceptions import MemoryError

__all__ = ["MemoryStore"]

DEFAULT_DATA_DIR = Path(__file__).parent / "data"


class MemoryStore:
    """FAISS-backed memory store for semantic search."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._index_file = self._data_dir / "faiss.index"
        self._memory_file = self._data_dir / "memory.json"
        self._dim_file = self._data_dir / "dim.txt"

        self._data_dir.mkdir(parents=True, exist_ok=True)

        if self._dim_file.exists():
            with open(self._dim_file, "r") as f:
                self.dim = int(f.read().strip())
        else:
            self.dim = 512  # BAAI/bge-small-zh-v1.5 default

        self.index: faiss.IndexFlatL2 = faiss.IndexFlatL2(self.dim)
        self.memories: list[dict[str, Any]] = []

        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if self._index_file.exists() and self._memory_file.exists():
            try:
                self.index = faiss.read_index(str(self._index_file))
                with open(self._memory_file, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load memory: {e}")
                self.index = faiss.IndexFlatL2(self.dim)
                self.memories = []

    def add(self, text: str) -> None:
        embedding = get_embedding(text)
        if embedding is None or len(embedding) == 0:
            return

        actual_dim = len(embedding)
        if actual_dim != self.dim:
            self.dim = actual_dim
            self.index = faiss.IndexFlatL2(self.dim)
            self._save_dim()

        self.index.add(np.array([embedding]).astype("float32"))
        self.memories.append({
            "text": text,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def delete(self, index: int) -> None:
        if index < 0 or index >= len(self.memories):
            raise MemoryError(
                f"Index {index} out of range (0-{len(self.memories) - 1})",
                index=index,
            )

        self.memories.pop(index)
        self.index = faiss.IndexFlatL2(self.dim)

        if self.memories:
            texts = [m["text"] for m in self.memories]
            embeddings = get_embeddings_batch(texts)
            for emb in embeddings:
                if emb is not None and len(emb) > 0:
                    self.index.add(np.array([emb]).astype("float32"))

        self._save()

    def delete_all(self) -> None:
        self.memories = []
        self.index = faiss.IndexFlatL2(self.dim)
        for fpath in [self._index_file, self._memory_file, self._dim_file]:
            try:
                fpath.unlink()
            except FileNotFoundError:
                pass

    def query(self, query_text: str, k: int = 3) -> list[tuple[dict[str, Any], float]]:
        if len(self.memories) == 0:
            return []

        query_vec = get_embedding(query_text)
        if query_vec is None or len(query_vec) == 0:
            return []

        query_vec = np.array([query_vec]).astype("float32")
        actual_k = min(k, len(self.memories))
        distances, indices = self.index.search(query_vec, actual_k)

        return [
            (self.memories[i], float(distances[0][j]))
            for j, i in enumerate(indices[0])
            if i < len(self.memories)
        ]

    def _save(self) -> None:
        faiss.write_index(self.index, str(self._index_file))
        with open(self._memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)
        self._save_dim()

    def _save_dim(self) -> None:
        with open(self._dim_file, "w") as f:
            f.write(str(self.dim))

    def __len__(self) -> int:
        return len(self.memories)

    def __repr__(self) -> str:
        return f"MemoryStore(dim={self.dim}, memories={len(self.memories)})"