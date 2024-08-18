#!/usr/bin/env python3
"""Tests for MemoryStore — uses simple hash embeddings (no model download required).

Run:
    USE_SIMPLE_EMBEDDING=true python -m pytest test_memory_store.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# Use simple hash embeddings for tests
os.environ["USE_SIMPLE_EMBEDDING"] = "true"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from exceptions import MemoryError
from memory_store import MemoryStore


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def store(temp_data_dir: Path) -> Generator[MemoryStore, None, None]:
    """MemoryStore backed by a temporary directory."""
    return MemoryStore(data_dir=temp_data_dir)


# ─── query() ──────────────────────────────────────────────────────────────────


def test_query_returns_list_of_tuples(store: MemoryStore) -> None:
    store.add("今天天气很好")
    store.add("工作压力很大")
    result = store.query("天气", k=1)
    assert isinstance(result, list)
    assert len(result) == 1
    item, dist = result[0]
    assert isinstance(item, dict)
    assert isinstance(dist, float)
    assert dist >= 0.0


def test_query_empty_store_returns_empty(store: MemoryStore) -> None:
    result = store.query("anything", k=3)
    assert result == []


def test_query_k_larger_than_store(store: MemoryStore) -> None:
    store.add("只有一条")
    result = store.query("一条", k=5)
    assert len(result) == 1


def test_query_tuple_distance_is_float(store: MemoryStore) -> None:
    store.add("压力")
    store.add("快乐")
    result = store.query("情绪", k=2)
    for _, dist in result:
        assert isinstance(dist, float)
        assert dist >= 0.0


# ─── delete() ─────────────────────────────────────────────────────────────────


def test_delete_reduces_count(store: MemoryStore) -> None:
    store.add("记忆一")
    store.add("记忆二")
    store.add("记忆三")
    store.delete(1)
    assert len(store.memories) == 2


def test_delete_removes_correct_item(store: MemoryStore) -> None:
    store.add("记忆一")
    store.add("记忆二")
    store.add("记忆三")
    store.delete(1)
    texts = [m["text"] for m in store.memories]
    assert "记忆一" in texts
    assert "记忆二" not in texts
    assert "记忆三" in texts


def test_delete_first_item(store: MemoryStore) -> None:
    store.add("第一条")
    store.add("第二条")
    store.delete(0)
    assert len(store.memories) == 1
    assert store.memories[0]["text"] == "第二条"


def test_delete_last_item(store: MemoryStore) -> None:
    store.add("第一条")
    store.add("第二条")
    store.delete(1)
    assert len(store.memories) == 1
    assert store.memories[0]["text"] == "第一条"


def test_delete_single_item_store(store: MemoryStore) -> None:
    store.add("唯一一条")
    store.delete(0)
    assert len(store.memories) == 0
    result = store.query("唯一", k=3)
    assert result == []


def test_delete_out_of_range_raises(store: MemoryStore) -> None:
    store.add("记忆一")
    with pytest.raises(MemoryError):
        store.delete(99)


def test_delete_negative_index_raises(store: MemoryStore) -> None:
    store.add("记忆一")
    with pytest.raises(MemoryError):
        store.delete(-1)


def test_delete_empty_store_raises(store: MemoryStore) -> None:
    with pytest.raises(MemoryError):
        store.delete(0)


def test_delete_persists_to_disk(store: MemoryStore, temp_data_dir: Path) -> None:
    store.add("要保留的记忆")
    store.add("要删除的记忆")
    store.delete(1)

    store2 = MemoryStore(data_dir=temp_data_dir)
    texts = [m["text"] for m in store2.memories]
    assert "要保留的记忆" in texts
    assert "要删除的记忆" not in texts


def test_delete_then_query_works(store: MemoryStore) -> None:
    store.add("工作很累")
    store.add("今天开心")
    store.add("压力很大")
    store.delete(1)

    result = store.query("工作", k=2)
    assert isinstance(result, list)
    texts_in_result = [m["text"] for m, _ in result]
    assert "今天开心" not in texts_in_result


# ─── delete_all() ─────────────────────────────────────────────────────────────


def test_delete_all_clears_memories(store: MemoryStore) -> None:
    store.add("记忆一")
    store.add("记忆二")
    store.delete_all()
    assert len(store.memories) == 0


def test_delete_all_removes_disk_files(store: MemoryStore, temp_data_dir: Path) -> None:
    store.add("测试记忆")
    store.delete_all()
    assert not (temp_data_dir / "faiss.index").exists()
    assert not (temp_data_dir / "memory.json").exists()
    assert not (temp_data_dir / "dim.txt").exists()


def test_delete_all_query_returns_empty(store: MemoryStore) -> None:
    store.add("记忆")
    store.delete_all()
    result = store.query("任何内容", k=3)
    assert result == []


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        env={**os.environ, "USE_SIMPLE_EMBEDDING": "true"},
    )
    sys.exit(result.returncode)