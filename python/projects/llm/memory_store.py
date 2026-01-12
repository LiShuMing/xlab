import faiss
import os
import json
import numpy as np
from datetime import datetime
from embeddings import get_embedding

DATA_DIR = "data"
INDEX_FILE = os.path.join(DATA_DIR, "faiss.index")
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")

os.makedirs(DATA_DIR, exist_ok=True)

class MemoryStore:
    def __init__(self, dim=1536):
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.memories = []

        if os.path.exists(INDEX_FILE) and os.path.exists(MEMORY_FILE):
            self.index = faiss.read_index(INDEX_FILE)
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                self.memories = json.load(f)

    def add(self, text):
        embedding = get_embedding(text)
        if embedding is None:
            return
        self.index.add(np.array([embedding]).astype('float32'))
        self.memories.append({
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        self.save()

    def query(self, query_text, k=3):
        if len(self.memories) == 0:
            return []
        query_vec = np.array([get_embedding(query_text)]).astype('float32')
        D, I = self.index.search(query_vec, k)
        return [self.memories[i] for i in I[0] if i < len(self.memories)]

    def save(self):
        faiss.write_index(self.index, INDEX_FILE)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)