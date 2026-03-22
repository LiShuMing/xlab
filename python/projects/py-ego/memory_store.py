import faiss
import os
import json
import numpy as np
from datetime import datetime
from embeddings import get_embedding, get_embeddings_batch

DATA_DIR = "data"
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")
DIM_FILE = os.path.join(DATA_DIR, "dim.txt")

os.makedirs(DATA_DIR, exist_ok=True)

class MemoryStore:
    def __init__(self, dim=None):
        # 如果指定了维度，使用指定维度；否则尝试从文件读取或使用默认值
        if dim is not None:
            self.dim = dim
        elif os.path.exists(DIM_FILE):
            with open(DIM_FILE, 'r') as f:
                self.dim = int(f.read().strip())
        else:
            # 默认维度：本地 BAAI/bge-small-zh-v1.5 模型为 512 维
            self.dim = 512

        self.index = faiss.IndexFlatL2(self.dim)
        self.memories = []

        if os.path.exists(INDEX_FILE) and os.path.exists(MEMORY_FILE):
            try:
                self.index = faiss.read_index(INDEX_FILE)
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
            except Exception as e:
                print(f"[MemoryStore] 加载历史数据失败: {e}，创建新的存储")
                self.index = faiss.IndexFlatL2(self.dim)
                self.memories = []

    def add(self, text):
        embedding = get_embedding(text)
        if embedding is None:
            return

        # 动态调整维度（如果 embedding 维度与当前不同）
        actual_dim = len(embedding)
        if actual_dim != self.dim:
            print(f"[MemoryStore] 检测到维度变化: {self.dim} -> {actual_dim}，重新创建索引")
            self.dim = actual_dim
            self.index = faiss.IndexFlatL2(self.dim)
            with open(DIM_FILE, 'w') as f:
                f.write(str(self.dim))

        self.index.add(np.array([embedding]).astype('float32'))
        self.memories.append({
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        self.save()

    def delete(self, index):
        """Delete a memory by positional index and rebuild the FAISS index.

        Rebuild uses get_embeddings_batch() for a single efficient forward pass.
        Skips any memory whose embedding returns None (embedding failure fallback).

        Raises IndexError if index is out of range.
        """
        if index < 0 or index >= len(self.memories):
            raise IndexError(f"索引 {index} 超出范围（共 {len(self.memories)} 条记忆）")

        self.memories.pop(index)

        # Rebuild FAISS index from remaining memories using batch embedding
        # (single forward pass, ~50x faster than N individual calls for local models)
        self.index = faiss.IndexFlatL2(self.dim)
        if self.memories:
            texts = [m['text'] for m in self.memories]
            embeddings = get_embeddings_batch(texts)
            for emb in embeddings:
                if emb is not None:  # Guard: skip failed embeddings
                    self.index.add(np.array([emb]).astype('float32'))

        self.save()

    def delete_all(self):
        """Clear all memories from memory and remove all disk files."""
        self.memories = []
        self.index = faiss.IndexFlatL2(self.dim)
        for fpath in [INDEX_FILE, MEMORY_FILE, DIM_FILE]:
            try:
                os.remove(fpath)
            except FileNotFoundError:
                pass

    def query(self, query_text, k=3):
        """Returns List[Tuple[dict, float]] — each tuple is (memory_dict, L2_distance)."""
        if len(self.memories) == 0:
            return []
        query_vec = get_embedding(query_text)
        if query_vec is None:
            return []
        query_vec = np.array([query_vec]).astype('float32')
        actual_k = min(k, len(self.memories))
        D, I = self.index.search(query_vec, actual_k)
        return [
            (self.memories[i], float(D[0][j]))
            for j, i in enumerate(I[0])
            if i < len(self.memories)
        ]

    def save(self):
        faiss.write_index(self.index, INDEX_FILE)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)
        with open(DIM_FILE, 'w') as f:
            f.write(str(self.dim))
