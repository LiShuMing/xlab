"""Document-level split before window construction, with provenance."""

import hashlib
import json
import random
from pathlib import Path

import torch

from .tokenizer import BOS, EOS, PAD, encode


def documents(path: Path | None = None) -> list[str]:
    if path is not None:
        docs = [
            line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    else:
        # Original synthetic corpus: useful for plumbing, not language capability claims.
        docs = [
            f"{name} likes {item}. {name} reads every day.\n"
            for name in ("Ada", "Ben", "Cleo", "Dora", "Evan", "Faye", "Gus", "Hope")
            for item in ("books", "music", "apples", "tea", "code", "art", "chess", "math")
        ]
    docs = list(dict.fromkeys(docs))
    if len(docs) < 4:
        raise ValueError("Need at least four distinct nonempty documents (one per line)")
    return docs


def prepare(path: Path | None, context: int, seed: int) -> tuple:
    docs = documents(path)
    random.Random(seed).shuffle(docs)
    cut = max(1, len(docs) // 5)
    valid_docs, train_docs = docs[:cut], docs[cut:]

    def windows(group: list[str]) -> tuple[torch.Tensor, torch.Tensor]:
        xs, ys = [], []
        for doc in group:
            tokens = [BOS] + encode(doc) + [EOS]
            for start in range(0, len(tokens) - 1, context):
                chunk = tokens[start : start + context + 1]
                x, y = chunk[:-1], chunk[1:]
                xs.append(x + [PAD] * (context - len(x)))
                ys.append(y + [PAD] * (context - len(y)))
        return torch.tensor(xs), torch.tensor(ys)

    metadata = {
        "source": str(path.resolve()) if path else "builtin-synthetic-v1",
        "sha256": hashlib.sha256(json.dumps(docs, ensure_ascii=False).encode()).hexdigest(),
        "train_documents": len(train_docs),
        "validation_documents": len(valid_docs),
        "split_seed": seed,
    }
    return windows(train_docs), windows(valid_docs), metadata
