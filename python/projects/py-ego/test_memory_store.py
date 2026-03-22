#!/usr/bin/env python3
"""
Tests for MemoryStore — uses simple hash embeddings (no model download required).

Run:
    USE_SIMPLE_EMBEDDING=true python -m pytest test_memory_store.py -v
    # or
    USE_SIMPLE_EMBEDDING=true python test_memory_store.py
"""
import os
import sys
import pytest

# Use simple hash embeddings for tests — no sentence-transformers needed
os.environ['USE_SIMPLE_EMBEDDING'] = 'true'

from memory_store import MemoryStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    """MemoryStore backed by a temporary directory — isolated per test."""
    import memory_store as ms_mod
    monkeypatch.setattr(ms_mod, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(ms_mod, 'INDEX_FILE', str(tmp_path / 'faiss.index'))
    monkeypatch.setattr(ms_mod, 'MEMORY_FILE', str(tmp_path / 'memory.json'))
    monkeypatch.setattr(ms_mod, 'DIM_FILE', str(tmp_path / 'dim.txt'))
    return MemoryStore()


# ─── query() ──────────────────────────────────────────────────────────────────

def test_query_returns_list_of_tuples(store):
    """query() must return List[Tuple[dict, float]], not List[dict]."""
    store.add("今天天气很好")
    store.add("工作压力很大")
    result = store.query("天气", k=1)
    assert isinstance(result, list)
    assert len(result) == 1
    item, dist = result[0]
    assert isinstance(item, dict)
    assert isinstance(dist, float)
    assert dist >= 0.0


def test_query_empty_store_returns_empty(store):
    """query() on empty store returns []."""
    result = store.query("anything", k=3)
    assert result == []


def test_query_k_larger_than_store(store):
    """query() with k > len(memories) returns len(memories) results, not k."""
    store.add("只有一条")
    result = store.query("一条", k=5)
    assert len(result) == 1


def test_query_tuple_distance_is_float(store):
    """Distance value in each tuple is a non-negative float."""
    store.add("压力")
    store.add("快乐")
    result = store.query("情绪", k=2)
    for _, dist in result:
        assert isinstance(dist, float)
        assert dist >= 0.0


# ─── delete() ─────────────────────────────────────────────────────────────────

def test_delete_reduces_count(store):
    """delete() removes exactly one memory."""
    store.add("记忆一")
    store.add("记忆二")
    store.add("记忆三")
    store.delete(1)
    assert len(store.memories) == 2


def test_delete_removes_correct_item(store):
    """delete(1) removes the second item, not the first or third."""
    store.add("记忆一")
    store.add("记忆二")
    store.add("记忆三")
    store.delete(1)
    texts = [m['text'] for m in store.memories]
    assert "记忆一" in texts
    assert "记忆二" not in texts
    assert "记忆三" in texts


def test_delete_first_item(store):
    """delete(0) removes the first memory."""
    store.add("第一条")
    store.add("第二条")
    store.delete(0)
    assert len(store.memories) == 1
    assert store.memories[0]['text'] == "第二条"


def test_delete_last_item(store):
    """delete(N-1) removes the last memory."""
    store.add("第一条")
    store.add("第二条")
    store.delete(1)
    assert len(store.memories) == 1
    assert store.memories[0]['text'] == "第一条"


def test_delete_single_item_store(store):
    """delete() on a 1-item store leaves an empty but valid store."""
    store.add("唯一一条")
    store.delete(0)
    assert len(store.memories) == 0
    result = store.query("唯一", k=3)
    assert result == []


def test_delete_out_of_range_raises(store):
    """delete() with an out-of-range index raises IndexError."""
    store.add("记忆一")
    with pytest.raises(IndexError):
        store.delete(99)


def test_delete_negative_index_raises(store):
    """delete() with a negative index raises IndexError."""
    store.add("记忆一")
    with pytest.raises(IndexError):
        store.delete(-1)


def test_delete_empty_store_raises(store):
    """delete() on empty store raises IndexError."""
    with pytest.raises(IndexError):
        store.delete(0)


def test_delete_persists_to_disk(store, tmp_path, monkeypatch):
    """After delete(), a new MemoryStore loaded from disk does not have the deleted item."""
    import memory_store as ms_mod
    monkeypatch.setattr(ms_mod, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(ms_mod, 'INDEX_FILE', str(tmp_path / 'faiss.index'))
    monkeypatch.setattr(ms_mod, 'MEMORY_FILE', str(tmp_path / 'memory.json'))
    monkeypatch.setattr(ms_mod, 'DIM_FILE', str(tmp_path / 'dim.txt'))

    store.add("要保留的记忆")
    store.add("要删除的记忆")
    store.delete(1)

    # Load from disk
    store2 = MemoryStore()
    texts = [m['text'] for m in store2.memories]
    assert "要保留的记忆" in texts
    assert "要删除的记忆" not in texts


def test_delete_then_query_works(store):
    """After delete(), query() still works correctly."""
    store.add("工作很累")
    store.add("今天开心")
    store.add("压力很大")
    store.delete(1)  # remove "今天开心"

    result = store.query("工作", k=2)
    assert isinstance(result, list)
    texts_in_result = [m['text'] for m, _ in result]
    assert "今天开心" not in texts_in_result


# ─── delete_all() ─────────────────────────────────────────────────────────────

def test_delete_all_clears_memories(store):
    """delete_all() removes all memories."""
    store.add("记忆一")
    store.add("记忆二")
    store.delete_all()
    assert len(store.memories) == 0


def test_delete_all_removes_disk_files(store, tmp_path):
    """delete_all() removes index, memory, and dim files from disk."""
    store.add("测试记忆")
    store.delete_all()
    assert not (tmp_path / 'faiss.index').exists()
    assert not (tmp_path / 'memory.json').exists()
    assert not (tmp_path / 'dim.txt').exists()


def test_delete_all_query_returns_empty(store):
    """After delete_all(), query() returns []."""
    store.add("记忆")
    store.delete_all()
    result = store.query("任何内容", k=3)
    assert result == []


if __name__ == "__main__":
    # Allow running directly: USE_SIMPLE_EMBEDDING=true python test_memory_store.py
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v"],
        env={**os.environ, 'USE_SIMPLE_EMBEDDING': 'true'}
    )
    sys.exit(result.returncode)
