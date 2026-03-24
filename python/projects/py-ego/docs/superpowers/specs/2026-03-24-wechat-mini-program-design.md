# WeChat Mini Program Design Specification

**Date:** 2026-03-24
**Status:** Draft
**Author:** Claude Code

---

## 1. Overview

### 1.1 Product Vision

A WeChat mini program for personal daily recording and AI-powered psychological Q&A. The app helps users:
- Record daily thoughts via text, voice, or photo
- Engage in personalized conversations with AI psychological companions
- Build a personal knowledge base that enhances AI understanding over time

### 1.2 Requirements Summary

| Dimension | Decision |
|-----------|----------|
| Product Type | Public-facing product |
| Core Features | Daily recording + Smart Q&A (equal priority) |
| Record Types | Voice, photo, text (3 input types) |
| Backend | Hybrid approach, reuse py-ego core logic |
| Cloud Provider | Alibaba Cloud (RDS PostgreSQL + OSS + Redis) |
| Frontend | Uni-app (Vue syntax) |
| Business Model | TBD, architecture extensible |

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 WeChat Mini Program (Uni-app)           │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   API Gateway (Nginx)                    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend Service                     │
│  ┌─────────────┬─────────────┬─────────────┬──────────┐ │
│  │ User Module │ Record      │ Chat        │ File     │ │
│  │ (WeChat)    │ (Voice/Photo│ (LLM+Memory)│ (OSS)    │ │
│  └─────────────┴─────────────┴─────────────┴──────────┘ │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Reuse py-ego Core Layer                            ││
│  │  - MemoryStore (adapted for multi-user)             ││
│  │  - RoleManager / ChatService                        ││
│  │  - Embeddings                                       ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ PostgreSQL    │   │ Redis         │   │ OSS           │
│ + pgvector    │   │ (cache)       │   │ (files)       │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 2.2 Design Decisions

1. **Monolith over microservices** - Simpler for MVP, can split later
2. **pgvector over FAISS** - One less component, natural user isolation
3. **Uni-app over native** - Vue syntax, cross-platform, faster development
4. **WeChat voice recognition** - No extra cost, simpler flow
5. **Alibaba Cloud** - Good integration with WeChat ecosystem in China

---

## 3. Database Design

### 3.1 Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    openid VARCHAR NOT NULL UNIQUE,  -- WeChat openid
    nickname VARCHAR(100),
    avatar_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP,
    deleted_at TIMESTAMP  -- Soft delete support
);

-- WeChat session (stores session_key for sensitive operations)
CREATE TABLE wechat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_key VARCHAR NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User profiles (layered: global + role-specific)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id VARCHAR DEFAULT 'therapist',
    global_profile TEXT,
    role_profiles JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily records
CREATE TABLE daily_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content_type VARCHAR(10) NOT NULL,  -- 'text', 'voice', 'photo'
    content TEXT,
    media_url VARCHAR,
    record_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS pgvector;

-- Semantic memories (with vectors)
-- Note: vector dimension must match EMBEDDING_DIMENSION in config
-- Default: 512 (BAAI/bge-small-zh-v1.5)
-- Alternative: 1536 (OpenAI text-embedding-3-small)
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    record_id UUID REFERENCES daily_records(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    embedding vector(512),  -- Configure via EMBEDDING_DIMENSION
    source_type VARCHAR(10) DEFAULT 'record',  -- 'record', 'chat'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create vector index
CREATE INDEX idx_memories_embedding ON memories
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id VARCHAR DEFAULT 'therapist',
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

-- Chat messages
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_daily_records_user_date ON daily_records(user_id, record_date DESC);
CREATE INDEX idx_memories_user ON memories(user_id);
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
```

### 3.2 Entity Relationships

```
users
  │
  ├──< user_profiles (1:1)
  │
  ├──< daily_records (1:N)
  │      │
  │      └──< memories (1:N)
  │
  ├──< memories (1:N)
  │
  └──< chat_sessions (1:N)
         │
         └──< chat_messages (1:N)
```

---

## 4. API Design

### 4.1 Standard Error Response

All API errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

**Common Error Codes:**
| Code | HTTP Status | Description |
|------|-------------|-------------|
| UNAUTHORIZED | 401 | Token invalid or expired |
| FORBIDDEN | 403 | No permission for this resource |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 422 | Request validation failed |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Server error |

### 4.2 Endpoints

#### Authentication

```
POST /api/auth/login
  Request:  { "code": "wx_login_code" }
  Response: { "token": "jwt_token", "refresh_token": "refresh_token", "user": {...} }
  Errors:   { "error": { "code": "WECHAT_AUTH_FAILED", "message": "..." } }

POST /api/auth/refresh
  Request:  { "refresh_token": "refresh_token" }
  Response: { "token": "new_jwt_token" }
  Errors:   { "error": { "code": "INVALID_REFRESH_TOKEN", "message": "..." } }
```

#### Records

```
POST /api/records
  Request:  { "content_type": "text|voice|photo", "content": "...", "media_url": "..." }
  Response: { "id": "uuid", "created_at": "..." }
  Errors:   { "error": { "code": "VALIDATION_ERROR", "message": "content is required" } }

GET /api/records?page=1&size=20&date=2026-03-24
  Response: { "items": [...], "total": 100, "page": 1, "size": 20 }

GET /api/records/{id}
  Response: { "id": "...", "content_type": "...", "content": "...", ... }
  Errors:   { "error": { "code": "NOT_FOUND", "message": "Record not found" } }

DELETE /api/records/{id}
  Response: { "success": true }

GET /api/records/timeline?month=2026-03
  Response: { "days": [{ "date": "2026-03-24", "count": 5, "preview": "..." }] }
```

#### File Upload (Photo)

```
POST /api/upload/presign
  Request:  { "filename": "photo.jpg", "content_type": "image/jpeg" }
  Response: { "upload_url": "https://oss...", "file_key": "users/xxx/photos/..." }

POST /api/upload/confirm
  Request:  { "file_key": "users/xxx/photos/..." }
  Response: { "media_url": "https://cdn.../..." }
```

#### Chat

```
POST /api/chat/sessions
  Request:  { "role_id": "therapist" }
  Response: { "id": "uuid", "role_id": "...", "started_at": "..." }

GET /api/chat/sessions?page=1&size=20
  Response: { "items": [...], "total": 50 }

POST /api/chat/sessions/{id}/messages
  Request:  { "content": "user message" }
  Response: { "reply": "AI response", "memories_used": 3 }

GET /api/chat/sessions/{id}/messages?before=uuid&limit=50
  Response: { "messages": [...], "has_more": true }
  Note: If 'before' is empty, returns the latest messages

PATCH /api/chat/sessions/{id}
  Request:  { "action": "end" }
  Response: { "success": true, "ended_at": "..." }

DELETE /api/chat/sessions/{id}
  Response: { "success": true }
```

#### Roles

```
GET /api/roles
  Response: { "roles": [{ "id": "therapist", "name": "心理陪护师", "icon": "brain" }, ...] }

GET /api/roles/current
  Response: { "role": {...} }

PUT /api/roles/current
  Request:  { "role_id": "researcher" }
  Response: { "success": true, "role": {...} }
```

#### Profile

```
GET /api/profile
  Response: { "global_profile": "...", "role_profiles": {...} }

PUT /api/profile
  Request:  { "global_profile": "...", "role_id": "therapist", "role_profile": "..." }
  Response: { "success": true }
```

### 4.3 Voice Input Flow

Uses WeChat built-in speech recognition (同声传译插件):

```
Mini Program                          Backend
     │                                   │
     │  1. User presses and speaks       │
     │  2. Plugin returns text           │
     │  3. User confirms/edits           │
     │                                   │
     │  4. POST /api/records             │
     │     { content_type: "voice",      │
     │       content: "transcribed" }    │
     │──────────────────────────────────▶│
     │                                   │
     │  5. Optional: upload voice to OSS │
     │     (if user wants to keep audio) │
     │                                   │
```

---

## 5. Backend Structure

### 5.1 Directory Layout

```
py-ego-miniapp/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Settings (Pydantic)
│   ├── dependencies.py            # DI container
│   │
│   ├── api/                       # API routes
│   │   ├── __init__.py
│   │   ├── auth.py                # POST /login, /refresh
│   │   ├── records.py             # CRUD for daily records
│   │   ├── chat.py                # Chat sessions and messages
│   │   ├── roles.py               # Role management
│   │   ├── profile.py             # User profile
│   │   └── upload.py              # File upload (OSS)
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py                # Base model class
│   │   ├── user.py
│   │   ├── record.py
│   │   ├── memory.py
│   │   ├── chat.py
│   │   └── profile.py
│   │
│   ├── schemas/                   # Pydantic request/response
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── record.py
│   │   ├── chat.py
│   │   └── profile.py
│   │
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py        # WeChat login
│   │   ├── record_service.py      # Record CRUD
│   │   ├── chat_service.py        # Chat (reuse py-ego)
│   │   ├── memory_service.py      # Memory (reuse py-ego)
│   │   ├── profile_service.py     # Profile (reuse py-ego)
│   │   └── role_service.py        # Role management
│   │
│   ├── core/                      # Reused from py-ego
│   │   ├── __init__.py
│   │   ├── embeddings.py          # Embedding generation
│   │   ├── memory_store.py        # Adapted: multi-user
│   │   ├── llm_client.py          # LLM API client
│   │   ├── role.py                # Role definitions
│   │   └── role_manager.py        # Adapted: multi-user
│   │
│   └── utils/
│       ├── __init__.py
│       ├── oss_client.py          # Alibaba OSS client
│       ├── jwt_handler.py         # JWT encode/decode
│       └── rate_limiter.py        # Request rate limiting
│
├── alembic/                       # Database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_records.py
│   ├── test_chat.py
│   └── test_memory.py
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

### 5.2 Key Adaptations from py-ego

#### MemoryStore (Multi-user Support)

```python
# app/core/memory_store.py
from sqlalchemy.orm import Session
from app.models.memory import Memory
from app.core.embeddings import get_embedding

class MemoryStore:
    """PostgreSQL + pgvector memory store with user isolation."""

    def __init__(self, db: Session, user_id: str):
        self._db = db
        self._user_id = user_id

    def add(self, text: str, source_type: str = "record", source_id: str | None = None) -> Memory:
        """Add a memory with embedding."""
        embedding = get_embedding(text)
        memory = Memory(
            user_id=self._user_id,
            content=text,
            embedding=embedding,
            source_type=source_type,
            record_id=source_id if source_type == "record" else None,
        )
        self._db.add(memory)
        self._db.commit()
        self._db.refresh(memory)
        return memory

    def query(self, query_text: str, k: int = 5) -> list[Memory]:
        """Semantic search with user isolation."""
        query_embedding = get_embedding(query_text)

        results = (
            self._db.query(Memory)
            .filter(Memory.user_id == self._user_id)
            .order_by(Memory.embedding.cosine_distance(query_embedding))
            .limit(k)
            .all()
        )
        return results

    def get_recent(self, limit: int = 10) -> list[Memory]:
        """Get recent memories for context."""
        return (
            self._db.query(Memory)
            .filter(Memory.user_id == self._user_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
            .all()
        )
```

#### ChatService (Adapted)

```python
# app/services/chat_service.py
from sqlalchemy.orm import Session
from app.core.memory_store import MemoryStore
from app.core.role_manager import RoleManager
from app.core.llm_client import LLMClient
from app.models.chat import ChatSession, ChatMessage

class ChatService:
    """Chat service orchestrating memory, profile, role, and LLM."""

    def __init__(self, db: Session, user_id: str, redis: Redis):
        self._db = db
        self._user_id = user_id
        self._memory_store = MemoryStore(db, user_id)
        self._role_manager = RoleManager(db, user_id)
        self._llm_client = LLMClient()
        self._redis = redis

    async def chat(self, session_id: str, user_input: str) -> str:
        """Process user message and generate response."""
        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_input,
        )
        self._db.add(user_msg)

        # Retrieve relevant memories
        memories = self._memory_store.query(user_input, k=3)

        # Get profile
        profile = self._role_manager.get_profile()

        # Get role system prompt
        system_prompt = self._role_manager.get_system_prompt()

        # Build context (reuse py-ego ChatContext pattern)
        messages = self._build_messages(system_prompt, memories, profile, user_input)

        # Call LLM
        reply = await self._llm_client.chat_completion(messages)

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        self._db.add(assistant_msg)

        # Add to memory (async)
        self._memory_store.add(user_input, source_type="chat")

        self._db.commit()

        return reply
```

---

## 6. Mini Program Frontend

### 6.1 Directory Layout

```
miniprogram/
├── src/
│   ├── App.vue                   # App entry
│   ├── main.js                   # Entry point
│   ├── manifest.json             # App config
│   ├── pages.json                # Page routes
│   │
│   ├── pages/
│   │   ├── index/                # Home (quick record)
│   │   │   └── index.vue
│   │   ├── record/               # Record detail/edit
│   │   │   └── index.vue
│   │   ├── chat/                 # Chat page
│   │   │   └── index.vue
│   │   ├── timeline/             # Timeline view
│   │   │   └── index.vue
│   │   ├── profile/              # Profile center
│   │   │   └── index.vue
│   │   └── role/                 # Role selection
│   │       └── index.vue
│   │
│   ├── components/
│   │   ├── NavBar.vue
│   │   ├── RecordCard.vue
│   │   ├── ChatBubble.vue
│   │   ├── VoiceInput.vue
│   │   └── RoleCard.vue
│   │
│   ├── api/
│   │   ├── request.js            # Axios wrapper
│   │   ├── auth.js
│   │   ├── record.js
│   │   ├── chat.js
│   │   └── role.js
│   │
│   ├── store/
│   │   ├── index.js
│   │   └── modules/
│   │       ├── user.js
│   │       ├── record.js
│   │       └── chat.js
│   │
│   ├── utils/
│   │   ├── auth.js               # Token management
│   │   ├── storage.js            # Local storage
│   │   └── voice.js              # Voice input
│   │
│   └── static/
│       └── images/
│
├── package.json
└── README.md
```

### 6.2 Page Flow

```
TabBar Navigation
┌─────────────────────────────────────────────────────────────┐
│    [Record]        [Chat]        [Timeline]        [Me]     │
└─────────────────────────────────────────────────────────────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│  Home     │  │  Chat     │  │  Timeline │  │  Profile  │
│           │  │           │  │           │  │           │
│ - Quick   │  │ - Role    │  │ - Calendar│  │ - Info    │
│   record  │  │   select  │  │ - List    │  │ - Roles   │
│ - Today's │  │ - Messages│  │ - Filter  │  │ - Settings│
│   records │  │ - Input   │  │           │  │           │
└───────────┘  └───────────┘  └───────────┘  └───────────┘
```

### 6.3 Home Page (Index)

```
┌─────────────────────────────────────────┐
│  📅 2026年3月24日                        │
│  晚上好，今天想记录什么？                  │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  ✏️ 文字  │ │  🎤 语音  │ │  📷 拍照  │   │
│  │  记录    │ │  记录    │ │  记录    │   │
│  └─────────┘ └─────────┘ └─────────┘   │
│                                         │
├─────────────────────────────────────────┤
│  今日记录                                │
│  ┌─────────────────────────────────────┐│
│  │ 📝 下午开了个会，讨论了新项目...        ││
│  │ 🎤 今天心情不错，天气很好...           ││
│  └─────────────────────────────────────┘│
│                                         │
├─────────────────────────────────────────┤
│  [Record]  [Chat]  [Timeline]  [Me]     │
└─────────────────────────────────────────┘
```

---

## 7. Deployment

### 7.1 MVP Stage

```
┌─────────────────────────────────────────────────────────┐
│                        MVP Deployment                    │
└─────────────────────────────────────────────────────────┘

         ┌─────────────┐
         │   Request   │
         └──────┬──────┘
                │
                ▼
    ┌───────────────────────┐
    │      Nginx            │
    │   (Reverse Proxy)     │
    │   + HTTPS             │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │   ECS (2vCPU 4GB)     │
    │   ┌─────────────────┐ │
    │   │    FastAPI      │ │
    │   │    (single)     │ │
    │   └─────────────────┘ │
    └───────────┬───────────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│ RDS    │ │ Redis  │ │  OSS   │
│(basic) │ │ (1GB)  │ │ (pay)  │
└────────┘ └────────┘ └────────┘
```

### 7.2 Cost Estimation

| Component | Spec | Monthly Cost |
|-----------|------|--------------|
| ECS | 2vCPU 4GB | ~100 RMB |
| RDS PostgreSQL | Basic, 20GB | ~200 RMB |
| Redis | 1GB | ~50 RMB |
| OSS | 10GB storage | ~10 RMB |
| Bandwidth | 1Mbps | ~50 RMB |
| **Total** | | **~400 RMB** |

### 7.3 Scaling Path

```
Stage 1: MVP (0-500 users)
├── Single ECS instance
├── Basic RDS
├── Basic Redis
└── Cost: ~400 RMB/month

Stage 2: Growth (500-5000 users)
├── 2-3 ECS + SLB
├── RDS HA (primary-replica)
├── Redis cluster
└── Cost: ~2000 RMB/month

Stage 3: Scale (5000+ users)
├── ECS cluster + auto-scaling
├── RDS HA + read replicas
├── Redis cluster
├── Migrate to Milvus (optional)
└── Cost: 5000+ RMB/month
```

---

## 8. Security

### 8.1 Authentication Flow

```
Mini Program                    Backend                    WeChat Server
     │                            │                             │
     │  1. wx.login()             │                             │
     │───────────────────────────▶│                             │
     │  2. code                   │                             │
     │◀───────────────────────────│                             │
     │                            │                             │
     │  3. POST /api/auth/login   │                             │
     │     { code }               │                             │
     │───────────────────────────▶│                             │
     │                            │  4. code2Session            │
     │                            │────────────────────────────▶│
     │                            │  5. openid + session_key    │
     │                            │◀────────────────────────────│
     │                            │                             │
     │                            │  6. Create/find user        │
     │                            │  7. Generate JWT            │
     │                            │                             │
     │  8. token + user info      │                             │
     │◀───────────────────────────│                             │
```

### 8.2 Token Strategy

- **Access Token**: JWT, 2 hours expiry
- **Refresh Token**: 7 days expiry, stored in Redis
- **Refresh**: Use refresh token to get new access token

### 8.3 Data Security

- User data isolation: All queries include `user_id` filter
- HTTPS everywhere
- OSS private access with signed URLs
- Profile data encrypted at rest (AES-256)

### 8.4 Rate Limiting

```python
# app/utils/rate_limiter.py
class RateLimiter:
    """Redis-based rate limiter with atomic operations."""

    def __init__(self, redis: Redis, max_requests: int = 100, window: int = 60):
        self._redis = redis
        self._max = max_requests
        self._window = window

    def check(self, user_id: str, endpoint: str) -> None:
        key = f"rate:{user_id}:{endpoint}"

        # Atomic increment - set expiry only on first increment
        current = self._redis.incr(key)
        if current == 1:
            self._redis.expire(key, self._window)

        if current > self._max:
            raise HTTPException(429, "Too many requests")
```

### 8.5 Compliance

- Privacy policy displayed on first login
- User data export endpoint: `GET /api/profile/export`
- User data deletion endpoint: `DELETE /api/profile` (soft delete, hard delete after 7 days)
- Content moderation via WeChat content security API

---

## 9. Implementation Phases

### Phase 1: Backend Core (Week 1-2)

- [ ] Project setup (FastAPI, SQLAlchemy, Alembic)
- [ ] Database migrations
- [ ] User model + WeChat login
- [ ] Record CRUD
- [ ] Basic chat (without memory)

### Phase 2: Intelligence (Week 3-4)

- [ ] Embedding service
- [ ] Memory store (pgvector)
- [ ] Role system
- [ ] Chat with memory
- [ ] Profile management

### Phase 3: Mini Program (Week 5-6)

- [ ] Uni-app project setup
- [ ] Home page with quick record
- [ ] Record list and detail
- [ ] Chat page
- [ ] Timeline page
- [ ] Profile page

### Phase 4: Integration & Deploy (Week 7-8)

- [ ] API integration
- [ ] Testing
- [ ] Alibaba Cloud setup
- [ ] CI/CD pipeline
- [ ] Production deployment
- [ ] WeChat mini program submission

---

## 10. Open Questions

1. **LLM Provider**: Kimi vs OpenAI vs other? (Consider cost, latency, quality)
2. **Content Moderation**: Use WeChat API or third-party?
3. **Audio Storage**: Keep original voice recordings or just text?
4. **Role Customization**: Allow users to create custom roles?
5. **Data Export Format**: JSON, Markdown, or other?

---

## Appendix A: Environment Variables

```bash
# .env

# App
APP_ENV=development
APP_SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/pyego_miniapp

# Redis
REDIS_URL=redis://localhost:6379/0

# WeChat
WECHAT_APP_ID=your-app-id
WECHAT_APP_SECRET=your-app-secret

# LLM
LLM_BASE_URL=https://api.kimi.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=kimi-for-coding

# Embedding (must match database vector dimension)
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DIMENSION=512
# Alternative for OpenAI:
# EMBEDDING_MODEL=text-embedding-3-small
# EMBEDDING_DIMENSION=1536

# OSS
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret
OSS_BUCKET_NAME=your-bucket
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```