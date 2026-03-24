# py-ego Change Logs

## 2026-03-24 - Feature: Role System Integration (Phase 3 Complete)

### Summary
Integrated the py-ego role system into the FastAPI backend, providing personalized AI personas with distinct personalities, knowledge bases, and speaking styles.

### New Components

**Role Module (`app/core/`)**
| File | Lines | Purpose |
|------|-------|---------|
| `role.py` | 450 | Role models with 4 predefined personas (therapist, researcher, learner, philosopher) |

**Role Service (`app/services/`)**
| File | Lines | Purpose |
|------|-------|---------|
| `role_service.py` | 60 | Role management service with system prompt generation |

**Role API (`app/api/`)**
| File | Lines | Purpose |
|------|-------|---------|
| `roles.py` | 115 | API endpoints for listing roles and getting role details |

**Role Schemas (`app/schemas/`)**
| File | Lines | Purpose |
|------|-------|---------|
| `role.py` | 85 | Pydantic models for role request/response validation |

### Updated Components

| File | Changes |
|------|---------|
| `app/api/__init__.py` | Added roles_router to API router |
| `app/schemas/__init__.py` | Exported RoleResponse and RoleDetailResponse |
| `app/services/chat_service.py` | Integrated role_service; uses role-specific system prompts based on session.role_id |

### Predefined Roles

| ID | Name | Icon | Description |
|----|------|------|-------------|
| therapist | 心理陪护师 | 🧠 | 专业的心理陪护，擅长认知行为疗法、情绪识别和情感共情 |
| researcher | 研究员 | 🔬 | 深入研究主题，生成研究报告和分析洞察 |
| learner | 学习者 | 📚 | 学习新技能，规划学习路径，巩固知识体系 |
| philosopher | 哲学家 | 🤔 | 思考人生终极问题，提供深刻的人生洞见 |

### Role System Features

1. **Personality System** - Background, traits, speaking style, catchphrases
2. **Knowledge Base** - Domain expertise, key concepts, classic quotes, references
3. **Example Dialogues** - Few-shot examples showing each role's speaking style
4. **Dynamic System Prompts** - Full prompt built from role configuration + memory context

### API Endpoints

```
GET /api/roles              # List all roles (summary)
GET /api/roles/{role_id}    # Get role details (full configuration)
```

### Integration with Chat

When a user sends a message in a chat session:
1. ChatService retrieves the session's `role_id`
2. RoleService builds the full system prompt with personality + knowledge + memory context
3. LLM receives the role-specific prompt for personalized responses

### Test Results
- 48/48 tests passing (40 existing + 8 new role tests)
- Role API endpoints verified
- Chat integration tested

### Next Steps (Phase 4)
- User role preference (current_role_id in User model)
- Role switching API
- Relationship memory for long-term user context

---

## 2026-03-24 - Feature: Intelligence Layer Implementation (Phase 2 Complete)

### Summary
Implemented LLM integration, semantic memory with pgvector, and memory-aware chat responses for the FastAPI backend.

### New Components

**Core Module (`app/core/`)**
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 15 | Package exports |
| `llm_client.py` | 130 | Async LLM client with httpx, OpenAI-compatible API |
| `embeddings.py` | 154 | Async embedding generation with sentence-transformers fallback |

**Memory System**
| File | Lines | Purpose |
|------|-------|---------|
| `models/memory.py` | 60 | Memory ORM model with pgvector Vector(512) column |
| `services/memory_service.py` | 130 | Memory operations: add, search (cosine similarity), delete |

**Updated Services**
| File | Changes |
|------|---------|
| `services/chat_service.py` | Integrated LLMClient and MemoryService; sends messages now generate AI responses with memory context |
| `services/record_service.py` | Creates memory entries when records are created; deletes memories when records are deleted |

### Key Features

1. **LLM Integration** - Async chat completions with proper error handling and fallback responses
2. **Semantic Memory** - pgvector-based storage with 512-dim embeddings (BAAI/bge-small-zh-v1.5)
3. **Memory-Aware Chat** - Retrieves relevant memories (k=5) for context in AI responses
4. **Automatic Memory Creation** - Records and chat conversations automatically stored as memories

### Architecture

```
User Message
    │
    ▼
┌─────────────────┐
│  ChatService    │
│  - Store msg    │
│  - Search mem   │
│  - Build ctx    │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌──────────┐
│  LLM  │  │ Memory   │
│Client │  │ Service  │
└───┬───┘  └────┬─────┘
    │           │
    ▼           ▼
┌───────┐  ┌──────────┐
│ LLM   │  │ pgvector │
│ API   │  │ (cosine) │
└───────┘  └──────────┘
```

### Test Results
- 40/40 tests passing
- Fixed test assertions (401 vs 403 for unauthorized access)

### Next Steps (Phase 3)
- Role system integration from py-ego core
- Role-specific system prompts and personalities
- Relationship memory for long-term user context

---

## 2026-03-24 - Feature: Backend Core Implementation (Phase 1 Complete)

### Summary
Implemented the FastAPI backend for the WeChat mini program with authentication, records API, and chat functionality.

### Project Structure

```
py-ego-miniapp/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # SQLAlchemy async engine
│   ├── dependencies.py         # DI: get_db, get_redis, get_current_user
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py             # User, WechatSession
│   │   ├── record.py           # DailyRecord
│   │   ├── profile.py          # UserProfile
│   │   └── chat.py             # ChatSession, ChatMessage
│   ├── schemas/                # Pydantic request/response
│   │   ├── auth.py             # LoginRequest, TokenResponse
│   │   ├── record.py           # RecordCreate, RecordResponse
│   │   └── chat.py             # SessionCreate, MessageCreate
│   ├── api/                    # API routes
│   │   ├── auth.py             # POST /login, /refresh
│   │   ├── records.py          # CRUD /records
│   │   └── chat.py             # Chat sessions & messages
│   ├── services/               # Business logic
│   │   ├── auth_service.py     # WeChat login, JWT
│   │   ├── record_service.py   # Record CRUD
│   │   └── chat_service.py     # Chat logic
│   └── utils/
│       ├── jwt_handler.py      # JWT encode/decode
│       └── exceptions.py       # Custom exceptions
└── tests/                      # 40 tests, all passing
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/login | WeChat login, returns JWT |
| POST | /api/auth/refresh | Refresh access token |
| POST | /api/records | Create daily record |
| GET | /api/records | List records (paginated) |
| GET | /api/records/timeline | Monthly timeline view |
| GET | /api/records/{id} | Get single record |
| DELETE | /api/records/{id} | Delete record |
| POST | /api/chat/sessions | Create chat session |
| GET | /api/chat/sessions | List chat sessions |
| PATCH | /api/chat/sessions/{id} | End session |
| DELETE | /api/chat/sessions/{id} | Delete session |
| POST | /api/chat/sessions/{id}/messages | Send message |
| GET | /api/chat/sessions/{id}/messages | List messages |

### Key Features

1. **WeChat Authentication** - OAuth login with JWT tokens
2. **Record Management** - CRUD for daily records (text/voice/photo)
3. **Chat System** - Sessions and messages (basic echo response)
4. **User Isolation** - All data scoped to authenticated user

### Test Results
- 40/40 tests passing
- Server starts correctly
- Health endpoint returns `{"status": "ok"}`

### Commits
- `dfe61c7` feat(backend): project setup with FastAPI and configuration
- `598697c` feat(backend): add SQLAlchemy models for user, record, profile, chat
- `...` feat(backend): add Pydantic schemas for API request/response
- `...` feat(backend): add JWT handler and custom exceptions
- `2761248` feat(backend): add auth service with WeChat login support
- `...` feat(backend): add auth API routes and FastAPI app entry
- `...` feat(backend): add records API with CRUD operations
- `...` feat(backend): add chat API with sessions and messages

### Next Steps (Phase 2)
- LLM integration for intelligent chat responses
- Memory store with pgvector for semantic search
- Role system integration from py-ego

---

## 2026-03-23 - Feature: English Comments & Command History

### Summary
Two enhancements:
1. Added bilingual (Chinese + English) comments to all role model fields
2. Implemented command history with up/down arrow key navigation

### Files Modified

| File | Changes |
|------|---------|
| `roles/role.py` | Added English comments to `RoleStyle`, `RoleKnowledge`, `RolePersonality`, `RoleExample`, `Role` classes and all their fields. Format: "English comment / 中文说明" |
| `main.py` | Added `setup_readline()` function for command history. Added `get_input_with_history()` wrapper. History persisted to `data/.input_history`. Max 1000 entries. |

### New Features

**Command History (上下键历史)**
- Up arrow (↑): Navigate to previous command
- Down arrow (↓): Navigate to next command
- History persists across sessions in `data/.input_history`
- Works on macOS/Linux (uses built-in `readline` module)

**Bilingual Field Comments**
```python
class RolePersonality(BaseModel):
    background: str  # Professional background... / 背景故事
    traits: list[str]  # Personality traits... / 性格特点
    speaking_style: str  # How the role communicates... / 说话风格
    catchphrases: list[str]  # Signature phrases... / 口头禅
```

### Test Results
- 17/17 tests passing
- Application runs correctly with history support

---

## 2026-03-23 - Docs: Added File Modification Policy

### Summary
Added a new rule to `CLAUDE.md` for file modification safety.

### File Modified
- `CLAUDE.md`: Added "File Modification Policy" section

### New Rule
```
# File Modification Policy
- **配置文件保护:** 不要擅自修改配置文件（如 `.env`、`settings.json`、`pyproject.toml` 等）。
- **目录边界:** 尽量不要修改本目录以外的文件。如果需要修改外部文件，务必同使用者再三确认。
- **确认流程:** 任何跨目录或配置相关的修改，必须：
  1. 明确告知用户要修改的文件路径
  2. 说明修改原因和内容
  3. 等待用户明确同意后再执行
```

---

## 2026-03-23 - Feature: Rich Role System with Character Depth

### Summary
Enhanced role system with four dimensions for richer, more immersive character interactions:
1. **背景故事 (Personality)** - Professional background, character traits, speaking style, catchphrases
2. **知识库 (Knowledge)** - Domain expertise, key concepts, classic quotes, references
3. **示例对话 (Examples)** - Few-shot dialogues showing the role's speaking style
4. **关系记忆 (Relationship)** - Long-term memory of interactions with each user

### New Models

```python
class RolePersonality(BaseModel):
    background: str              # "你在北京大学心理学系深造..."
    traits: list[str]            # ["温和", "耐心", "共情", "专业"]
    speaking_style: str          # "温暖、理解、引导式提问..."
    catchphrases: list[str]      # ["我听到了你的感受", "我们一起来看看"]

class RoleKnowledge(BaseModel):
    domain_expertise: list[str]  # ["认知行为疗法", "正念减压"]
    key_concepts: list[str]      # ["认知扭曲", "情绪颗粒度"]
    classic_quotes: list[str]    # ["「情绪就像天气...」"]
    references: list[str]        # ["《认知疗法》- Judith Beck"]

class RoleExample(BaseModel):
    context: str | None          # "用户表达了焦虑情绪"
    user_input: str              # "最近总是睡不着..."
    assistant_response: str      # "听起来工作压力让你很困扰..."
```

### Files Modified

| File | Changes |
|------|---------|
| `roles/role.py` | Added `RolePersonality`, `RoleKnowledge`, `RoleExample` models. Added `build_full_system_prompt()` and `build_examples_context()` methods. Enriched all 4 predefined roles with detailed personality, knowledge, and examples. |
| `roles/role_manager.py` | Added `RelationshipManager` class for relationship memory. Added `get_system_prompt()` that combines all dimensions. Added `get_examples_context()` for few-shot learning. |
| `chat_service.py` | Updated `ChatContext` to include examples. Uses `get_system_prompt()` for full prompt with personality/knowledge/relationship. |

### Predefined Role Details

**心理陪护师 (Therapist)**
- 背景：北大心理学博士，5000+小时咨询经验
- 特点：温和、耐心、共情、不评判
- 领域：CBT、正念减压、情绪聚焦疗法
- 口头禅："我听到了你的感受"、"你愿意多说说吗？"

**研究员 (Researcher)**
- 背景：清华社科博士，顶级智库工作经历
- 特点：严谨、客观、逻辑性强
- 领域：社会科学研究方法、政策分析
- 口头禅："从研究的角度来看"、"数据显示"

**学习者 (Learner)**
- 背景：学习科学研究者，终身学习践行者
- 特点：耐心、鼓励型、善于比喻
- 领域：认知科学、间隔重复、费曼学习法
- 口头禅："让我们一步步来"、"试试这个练习"

**哲学家 (Philosopher)**
- 背景：哈佛哲学系深造，专攻存在主义和东方哲学
- 特点：深邃、温和、善问、开放
- 领域：存在主义、东方哲学、伦理学
- 口头禅："这让我想起"、"你有没有想过"

### System Prompt Construction

The full system prompt is now built dynamically:

```
[Base system prompt]

## 你的背景
[personality.background]

## 你的性格特点
[personality.traits joined]

## 你的说话风格
[personality.speaking_style]

## 你常用的表达方式
[personality.catchphrases]

## 你的专业领域
[knowledge.domain_expertise joined]

## 你熟悉的核心概念
[knowledge.key_concepts bulleted]

## 你可以引用的经典语录
[knowledge.classic_quotes bulleted]

## 你与用户的关系记忆
[relationship memory]
```

### Data Structure

```
data/
├── profile.md                    # 全局画像
├── profile_therapist.md          # 心理陪护师专属画像
├── relationship_therapist.md     # 与心理陪护师的关系记忆
├── therapist/
│   ├── memory.json
│   ├── faiss.index
│   └── dim.txt
├── researcher/
│   └── ...
└── ...
```

### Test Results
- 17/17 tests passing
- Role switching works correctly
- Rich system prompt builds correctly

---

## 2026-03-23 - Feature: Multi-Agent Role System

### Summary
Implemented a multi-role system that abstracts the therapist persona into a configurable agent system.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `roles/__init__.py` | 6 | Role package initialization |
| `roles/role.py` | 185 | `Role` Pydantic model with predefined roles |
| `roles/role_manager.py` | 145 | `RoleManager` for loading, switching roles |

### Files Modified

| File | Changes |
|------|---------|
| `profile.py` | Added layered profile support: global + role-specific |
| `chat_service.py` | Now accepts `RoleManager`, delegates memory/profile to role manager |
| `cli/ui.py` | All print methods accept optional `Role` parameter |
| `cli/commands.py` | Added `/role`, `/roles`, `/roleinfo` commands |
| `main.py` | Initializes `RoleManager`, prompt shows role icon |

### Design Decisions
1. **独立记忆**: Each role has its own `data/{role_id}/` directory
2. **分层画像**: Global `profile.md` + role-specific `profile_{role_id}.md`

---

## 2026-03-23 - Major Refactoring: Modern Python & AI Agent Architecture

### Summary
Refactored the entire codebase to align with CLAUDE.md standards.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `exceptions.py` | 55 | Custom exception hierarchy |
| `models.py` | 70 | Pydantic models |
| `llm_client.py` | 96 | LLM client wrapper |
| `chat_service.py` | 138 | Core chat business logic |
| `profile.py` | 111 | User profile management |
| `cli/__init__.py` | 6 | CLI package |
| `cli/ui.py` | 271 | Terminal UI utilities |
| `cli/commands.py` | 119 | Slash command handlers |

### Files Modified

| File | Changes |
|------|---------|
| `config.py` | Migrated to Pydantic Settings |
| `embeddings.py` | Added type hints, silent fallback |
| `memory_store.py` | Added type hints, configurable data_dir |
| `main.py` | Simplified to thin entry point |
| `requirements.txt` | Added pydantic, structlog |

### Test Results
- 17/17 tests passing
- Application starts correctly

---

## 2026-03-24 - Design: WeChat Mini Program Architecture

### Summary
Designed a WeChat mini program for daily recording and AI-powered psychological Q&A, based on existing py-ego codebase.

### Requirements Summary

| Dimension | Decision |
|-----------|----------|
| Product Type | Public-facing product |
| Core Features | Daily recording + Smart Q&A (equal priority) |
| Record Types | Voice, photo, text (3 input types) |
| Backend | Hybrid approach, reuse py-ego core logic |
| Cloud Provider | Alibaba Cloud (RDS PostgreSQL + OSS + Redis) |
| Frontend | Uni-app (Vue syntax) |
| Business Model | TBD, architecture extensible |

### Architecture: Monolith + Modular Design

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

### Database Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    openid VARCHAR NOT NULL UNIQUE,  -- WeChat openid
    nickname VARCHAR,
    avatar_url VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP
);

-- User profiles (layered: global + role-specific)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    role_id VARCHAR DEFAULT 'therapist',
    global_profile TEXT,
    role_profiles JSONB,
    updated_at TIMESTAMP
);

-- Daily records
CREATE TABLE daily_records (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    content_type VARCHAR(10),  -- 'text', 'voice', 'photo'
    content TEXT,
    media_url VARCHAR,
    record_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Semantic memories (with vectors)
CREATE EXTENSION pgvector;

CREATE TABLE memories (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    record_id UUID REFERENCES daily_records(id),
    content TEXT,
    embedding vector(512),
    source_type VARCHAR(10),  -- 'record', 'chat'
    created_at TIMESTAMP
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    role_id VARCHAR,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

-- Chat messages
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id),
    role VARCHAR(10),  -- 'user', 'assistant'
    content TEXT,
    created_at TIMESTAMP
);
```

### API Design

```
/api/auth
├── POST /login          # WeChat login, return JWT
└── POST /refresh        # Refresh token

/api/records
├── POST /               # Create record (text/voice/photo)
├── GET /                # List records (paginated, by date)
├── GET /{id}            # Get record detail
├── DELETE /{id}         # Delete record
└── GET /timeline        # Timeline view

/api/chat
├── POST /sessions       # Create new session
├── GET /sessions        # List sessions
├── POST /sessions/{id}/messages  # Send message, get reply
├── GET /sessions/{id}/messages   # Get message history
└── DELETE /sessions/{id}         # Delete session

/api/roles
├── GET /                # List available roles
├── GET /current         # Get current role
└── PUT /current         # Switch role

/api/profile
├── GET /                # Get current profile
└── PUT /                # Update profile
```

### Backend Structure

```
py-ego-miniapp/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── api/                    # API routes
│   │   ├── auth.py
│   │   ├── records.py
│   │   ├── chat.py
│   │   ├── roles.py
│   │   └── profile.py
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   │   ├── auth_service.py
│   │   ├── record_service.py
│   │   ├── chat_service.py
│   │   ├── memory_service.py
│   │   └── role_service.py
│   ├── core/                   # Reused from py-ego
│   │   ├── embeddings.py
│   │   ├── memory_store.py     # Adapted: multi-user support
│   │   ├── llm_client.py
│   │   └── role.py
│   └── utils/
│       ├── oss_client.py
│       └── jwt_handler.py
├── alembic/
├── tests/
└── requirements.txt
```

### Mini Program Frontend Structure

```
miniprogram/
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── pages.json
│   ├── pages/
│   │   ├── index/        # Home (quick record)
│   │   ├── record/       # Record page
│   │   ├── chat/         # Chat page
│   │   ├── timeline/     # Timeline view
│   │   ├── profile/      # Profile center
│   │   └── role/         # Role selection
│   ├── components/
│   │   ├── NavBar.vue
│   │   ├── RecordCard.vue
│   │   ├── ChatBubble.vue
│   │   └── VoiceInput.vue
│   ├── api/              # API requests
│   ├── store/            # Vuex modules
│   └── utils/
└── package.json
```

### Vector Storage: PostgreSQL pgvector

Chosen over FAISS for:
- Simpler architecture (no extra component)
- Natural user isolation (WHERE user_id = ?)
- Hybrid queries (filter + vector search)
- Alibaba Cloud RDS support
- Acceptable performance for MVP (millions of vectors)

```python
# core/memory_store.py (adapted)
class MemoryStore:
    def __init__(self, db: Session, user_id: str):
        self._db = db
        self._user_id = user_id

    def add(self, text: str, source_type: str = "record") -> Memory:
        embedding = get_embedding(text)
        memory = Memory(
            user_id=self._user_id,
            content=text,
            embedding=embedding,
            source_type=source_type,
        )
        self._db.add(memory)
        self._db.commit()
        return memory

    def query(self, query_text: str, k: int = 5) -> list[Memory]:
        query_embedding = get_embedding(query_text)
        return self._db.query(Memory).filter(
            Memory.user_id == self._user_id
        ).order_by(
            Memory.embedding.cosine_distance(query_embedding)
        ).limit(k).all()
```

### Deployment: MVP Stage

```
┌─────────────────────────────────────────┐
│              Nginx (HTTPS)               │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│         ECS (2vCPU 4GB)                 │
│         FastAPI (single instance)       │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌────────┐  ┌────────┐
│ RDS    │  │ Redis  │  │  OSS   │
│ (basic)│  │ (1GB)  │  │ (pay)  │
└────────┘  └────────┘  └────────┘

Estimated Cost: ~400 RMB/month (MVP)
```

### Security & Compliance

**Authentication:**
- WeChat OAuth login (no password storage)
- JWT access token (2 hours expiry)
- Refresh token (7 days, stored in Redis)

**Data Security:**
- User data isolation (mandatory user_id filter)
- HTTPS everywhere
- Private OSS access (signed URLs)

**Rate Limiting:**
- 100 requests/minute per user (Redis counter)

**Compliance:**
- Privacy policy on first login
- User data export/delete endpoints
- Content moderation (WeChat API)

### Voice Input Flow (Simplified)

Uses WeChat built-in speech recognition (同声传译插件):
1. User presses and speaks
2. Plugin returns transcribed text directly
3. No backend voice service needed
4. Original voice file optional (user choice)

### Design Decisions

1. **Monolith over microservices** - Simpler for MVP, can split later
2. **pgvector over FAISS** - One less component, natural user isolation
3. **Uni-app over native** - Vue syntax, cross-platform, faster development
4. **WeChat voice recognition** - No extra cost, simpler flow
5. **Alibaba Cloud** - Good integration with WeChat ecosystem in China

### Next Steps

1. Set up project structure
2. Implement backend core (auth, user, records)
3. Implement chat service with memory
4. Build mini program UI
5. Deploy to Alibaba Cloud

### Spec Review Fixes (2026-03-24)

Addressed issues from code review:

**Critical Fixes:**
1. Added `wechat_sessions` table for storing session_key
2. Added standard error response format with error codes
3. Added `PATCH /api/chat/sessions/{id}` for ending sessions
4. Added `deleted_at` field to users table for soft delete

**Major Fixes:**
1. Added embedding model/dimension configuration in env vars
2. Added photo upload API (`POST /api/upload/presign`, `POST /api/upload/confirm`)
3. Added `has_more` field to chat messages pagination
4. Fixed rate limiter race condition with atomic `incr` operation

**Minor Fixes:**
1. Changed role icons from emoji to string identifiers
2. Added `has_more` field for message pagination

---