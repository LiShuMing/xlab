# Intelligence Layer Implementation Plan (Phase 2)

> **Goal:** Integrate LLM, memory, and role systems into the FastAPI backend for intelligent chat responses.

**Architecture:** Extend the existing FastAPI backend with:
- LLM service for chat completions
- pgvector-based memory store for semantic search
- Role system integration from py-ego core

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pgvector, OpenAI-compatible LLM API, sentence-transformers

---

## File Structure

```
py-ego-miniapp/
├── app/
│   ├── core/                   # Reused/adapted from py-ego
│   │   ├── __init__.py
│   │   ├── llm_client.py       # Async LLM client
│   │   ├── embeddings.py       # Embedding generation
│   │   ├── role.py             # Role models
│   │   └── role_manager.py     # Role management
│   │
│   ├── services/
│   │   ├── memory_service.py   # pgvector memory operations
│   │   └── chat_service.py     # Updated with LLM integration
│   │
│   └── models/
│       └── memory.py           # Memory ORM model
```

---

## Task 1: Create Core Module with LLM Client

**Files:**
- Create: `py-ego-miniapp/app/core/__init__.py`
- Create: `py-ego-miniapp/app/core/llm_client.py`

### Step 1.1: Create core package

```bash
mkdir -p py-ego-miniapp/app/core
```

### Step 1.2: Create async LLM client

```python
# app/core/llm_client.py
"""Async LLM client for chat completions."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI-compatible async LLM client."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=self._settings.llm_base_url,
            headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
            timeout=60.0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send async chat completion request."""
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> str:
    """Convenience function for single completion."""
    client = LLMClient()
    try:
        return await client.chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
    finally:
        await client.close()
```

---

## Task 2: Create Embedding Module

**Files:**
- Create: `py-ego-miniapp/app/core/embeddings.py`

### Step 2.1: Create async embedding module

```python
# app/core/embeddings.py
"""Async embedding generation with fallback strategies."""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.config import get_settings

logger = logging.getLogger(__name__)

# Environment setup for ML libraries
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

_local_embedder: Any = None


def _simple_hash_embedding(text: str, dim: int = 512) -> NDArray[np.float32]:
    """Generate deterministic hash-based embedding (fallback)."""
    seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def _get_local_embedder() -> Any:
    """Get local embedding model (lazy loaded)."""
    global _local_embedder
    if _local_embedder is None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        _local_embedder = SentenceTransformer(settings.embedding_model, device="cpu")
    return _local_embedder


async def get_embedding(text: str) -> NDArray[np.float32]:
    """Get embedding vector for text (sync in thread pool)."""
    import asyncio

    cleaned = text.strip() if text else ""
    if not cleaned:
        cleaned = ""

    settings = get_settings()

    try:
        embedder = _get_local_embedder()
        # Run sync embedding in thread pool
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: embedder.encode(
                cleaned,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )
        return embedding.astype(np.float32)
    except Exception as e:
        logger.warning(f"Embedding failed, using hash fallback: {e}")
        return _simple_hash_embedding(cleaned, settings.embedding_dimension)


async def get_embeddings_batch(texts: list[str]) -> list[NDArray[np.float32]]:
    """Get embeddings for multiple texts."""
    import asyncio

    if not texts:
        return []

    settings = get_settings()
    cleaned = [t.strip() if t else "" for t in texts]

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
            )
        )
        return [e.astype(np.float32) for e in embeddings]
    except Exception as e:
        logger.warning(f"Batch embedding failed, using hash fallback: {e}")
        return [_simple_hash_embedding(t, settings.embedding_dimension) for t in cleaned]
```

---

## Task 3: Create Memory Model

**Files:**
- Modify: `py-ego-miniapp/app/models/__init__.py`
- Create: `py-ego-miniapp/app/models/memory.py`

### Step 3.1: Create Memory ORM model

```python
# app/models/memory.py
"""Memory model for semantic search with pgvector."""
from __future__ import annotations

from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Memory(Base):
    """Semantic memory stored with vector embeddings.

    Attributes:
        id: Primary key UUID.
        user_id: Foreign key to users table.
        content: Text content of the memory.
        embedding: Vector embedding for semantic search.
        source_type: Origin of memory ('record', 'chat').
        source_id: Optional reference to source record/message.
    """

    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("daily_records.id", ondelete="SET NULL"), nullable=True)
```

### Step 3.2: Update models init

Add Memory import to `app/models/__init__.py`.

---

## Task 4: Create Memory Service

**Files:**
- Create: `py-ego-miniapp/app/services/memory_service.py`

### Step 4.1: Create memory service

```python
# app/services/memory_service.py
"""Memory service for semantic search operations."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedding
from app.models import Memory, User


class MemoryService:
    """Service for memory operations with pgvector."""

    def __init__(self, db: AsyncSession, user: User):
        self._db = db
        self._user = user

    async def add_memory(
        self,
        content: str,
        source_type: str,
        source_id: UUID | None = None,
    ) -> Memory:
        """Add a new memory with embedding."""
        embedding = await get_embedding(content)

        memory = Memory(
            user_id=self._user.id,
            content=content,
            embedding=embedding.tolist(),
            source_type=source_type,
            source_id=source_id,
        )
        self._db.add(memory)
        await self._db.commit()
        await self._db.refresh(memory)
        return memory

    async def search_memories(
        self,
        query: str,
        k: int = 5,
    ) -> list[Memory]:
        """Search memories by semantic similarity."""
        query_embedding = await get_embedding(query)

        # Use pgvector cosine distance
        result = await self._db.execute(
            select(Memory)
            .where(Memory.user_id == self._user.id)
            .order_by(Memory.embedding.cosine_distance(query_embedding.tolist()))
            .limit(k)
        )
        return list(result.scalars().all())

    async def get_memories_for_record(self, record_id: UUID) -> list[Memory]:
        """Get all memories associated with a record."""
        result = await self._db.execute(
            select(Memory)
            .where(
                Memory.user_id == self._user.id,
                Memory.source_id == record_id,
            )
        )
        return list(result.scalars().all())

    async def delete_memory(self, memory_id: UUID) -> None:
        """Delete a memory by ID."""
        result = await self._db.execute(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.user_id == self._user.id,
            )
        )
        memory = result.scalar_one_or_none()
        if memory:
            await self._db.delete(memory)
            await self._db.commit()
```

---

## Task 5: Update Chat Service with LLM Integration

**Files:**
- Modify: `py-ego-miniapp/app/services/chat_service.py`

### Step 5.1: Integrate LLM and memory into chat

Update the chat service to:
1. Search relevant memories before responding
2. Build context with memories
3. Call LLM for response
4. Store conversation as memories

---

## Task 6: Create Database Migration

**Files:**
- Create: Alembic migration for memories table

### Step 6.1: Generate migration

```bash
cd py-ego-miniapp
alembic revision --autogenerate -m "add memories table"
alembic upgrade head
```

---

## Task 7: Update Tests

**Files:**
- Create: `py-ego-miniapp/tests/test_memory.py`
- Modify: `py-ego-miniapp/tests/test_chat_api.py` (update for LLM responses)

---

## Verification Steps

1. Run tests: `pytest tests/ -v`
2. Test LLM integration: Send chat message, verify non-echo response
3. Test memory search: Create record, verify it appears in memory search
4. Test role-based responses: Different roles should have different tones

---

## Dependencies to Add

Add to `requirements.txt`:
```
pgvector==0.2.4
sentence-transformers==2.3.1
```
