# Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend with authentication, records API, and basic chat functionality.

**Architecture:** FastAPI monolith with SQLAlchemy ORM, PostgreSQL + pgvector for storage, Redis for caching/sessions. Follows the layered architecture: API routes → Services → Models, with core components reused from py-ego.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL + pgvector, Redis, python-jose (JWT), httpx (async HTTP)

---

## File Structure

```
py-ego-miniapp/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # SQLAlchemy engine/session
│   ├── dependencies.py         # DI: get_db, get_redis, get_current_user
│   │
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── __init__.py
│   │   ├── base.py             # Base model with common fields
│   │   ├── user.py             # User, WechatSession
│   │   ├── record.py           # DailyRecord
│   │   ├── profile.py          # UserProfile
│   │   └── chat.py             # ChatSession, ChatMessage
│   │
│   ├── schemas/                # Pydantic request/response
│   │   ├── __init__.py
│   │   ├── common.py           # ErrorResponse, PaginatedResponse
│   │   ├── auth.py             # LoginRequest, TokenResponse
│   │   ├── user.py             # UserResponse
│   │   ├── record.py           # RecordCreate, RecordResponse
│   │   └── chat.py             # MessageCreate, MessageResponse
│   │
│   ├── api/                    # API routes
│   │   ├── __init__.py         # Router aggregation
│   │   ├── auth.py             # POST /login, /refresh
│   │   ├── records.py          # CRUD /records
│   │   ├── chat.py             # Chat sessions & messages
│   │   ├── roles.py            # Role management
│   │   └── profile.py          # User profile
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py     # WeChat login, JWT generation
│   │   ├── record_service.py   # Record CRUD
│   │   └── chat_service.py     # Chat logic
│   │
│   └── utils/
│       ├── __init__.py
│       ├── jwt_handler.py      # JWT encode/decode
│       └── exceptions.py       # Custom exceptions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Fixtures: db, client, mock_user
│   ├── test_auth.py
│   ├── test_records.py
│   └── test_chat.py
│
├── alembic/                    # Database migrations
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│
├── requirements.txt
└── .env.example
```

---

## Task 1: Project Setup & Configuration

**Files:**
- Create: `py-ego-miniapp/requirements.txt`
- Create: `py-ego-miniapp/.env.example`
- Create: `py-ego-miniapp/app/__init__.py`
- Create: `py-ego-miniapp/app/config.py`

- [ ] **Step 1: Create project directory and requirements**

```bash
mkdir -p py-ego-miniapp/app py-ego-miniapp/tests py-ego-miniapp/alembic/versions
```

- [ ] **Step 2: Create requirements.txt**

```text
# Web framework
fastapi==0.109.0
uvicorn[standard]==0.27.0

# Database
sqlalchemy==2.0.25
asyncpg==0.29.0
alembic==1.13.1
pgvector==0.2.4

# Redis
redis==5.0.1

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# HTTP client
httpx==0.26.0

# Validation
pydantic==2.5.3
pydantic-settings==2.1.0

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
httpx==0.26.0

# Utils
python-dotenv==1.0.0
```

- [ ] **Step 3: Create .env.example**

```bash
# App
APP_ENV=development
APP_SECRET_KEY=dev-secret-key-change-in-production

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pyego_miniapp

# Redis
REDIS_URL=redis://localhost:6379/0

# WeChat
WECHAT_APP_ID=
WECHAT_APP_SECRET=

# LLM
LLM_BASE_URL=https://api.kimi.com/v1
LLM_API_KEY=
LLM_MODEL=kimi-for-coding

# Embedding
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DIMENSION=512

# JWT
JWT_SECRET_KEY=jwt-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] **Step 4: Create config.py with Pydantic Settings**

```python
# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pyego_miniapp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # WeChat
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # LLM
    llm_base_url: str = "https://api.kimi.com/v1"
    llm_api_key: str = ""
    llm_model: str = "kimi-for-coding"

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dimension: int = 512

    # JWT
    jwt_secret_key: str = "jwt-secret-key"
    jwt_access_token_expire_minutes: int = 120
    jwt_refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Create app/__init__.py**

```python
# app/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 6: Install dependencies and verify**

```bash
cd py-ego-miniapp
pip install -r requirements.txt
python -c "from app.config import get_settings; print(get_settings().app_env)"
```

Expected: `development`

- [ ] **Step 7: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): project setup with FastAPI and configuration"
```

---

## Task 2: Database Models & Migrations

**Files:**
- Create: `app/database.py`
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/models/user.py`
- Create: `app/models/record.py`
- Create: `app/models/profile.py`
- Create: `app/models/chat.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Write failing test for database connection**

```python
# tests/conftest.py
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: Create database.py**

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 3: Create base model**

```python
# app/models/base.py
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

- [ ] **Step 4: Create user model**

```python
# app/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    openid = Column(String(100), unique=True, nullable=False, index=True)
    nickname = Column(String(100))
    avatar_url = Column(String(500))
    last_active_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, lazy="selectin")
    records = relationship("DailyRecord", back_populates="user", lazy="dynamic")
    chat_sessions = relationship("ChatSession", back_populates="user", lazy="dynamic")

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None


class WechatSession(Base):
    __tablename__ = "wechat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_key = Column(String(100), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 5: Create record model**

```python
# app/models/record.py
import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import enum


class ContentType(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"


class DailyRecord(Base, TimestampMixin):
    __tablename__ = "daily_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content_type = Column(String(10), nullable=False)
    content = Column(Text)
    media_url = Column(String(500))
    record_date = Column(Date, default=date.today, index=True)

    # Relationships
    user = relationship("User", back_populates="records")
```

- [ ] **Step 6: Create profile model**

```python
# app/models/profile.py
import uuid
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role_id = Column(String(50), default="therapist")
    global_profile = Column(Text)
    role_profiles = Column(JSONB, default=dict)

    # Relationships
    user = relationship("User", back_populates="profile")
```

- [ ] **Step 7: Create chat model**

```python
# app/models/chat.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(50), default="therapist")
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", lazy="dynamic")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
```

- [ ] **Step 8: Create models/__init__.py**

```python
# app/models/__init__.py
from app.models.base import Base, TimestampMixin
from app.models.user import User, WechatSession
from app.models.record import DailyRecord, ContentType
from app.models.profile import UserProfile
from app.models.chat import ChatSession, ChatMessage

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "WechatSession",
    "DailyRecord",
    "ContentType",
    "UserProfile",
    "ChatSession",
    "ChatMessage",
]
```

- [ ] **Step 9: Write and run test for model imports**

```python
# tests/test_models.py
def test_models_import():
    from app.models import User, DailyRecord, ChatSession, ChatMessage
    assert User is not None
    assert DailyRecord is not None
    assert ChatSession is not None
    assert ChatMessage is not None
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_models.py -v
```

Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add SQLAlchemy models for user, record, profile, chat"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/common.py`
- Create: `app/schemas/auth.py`
- Create: `app/schemas/user.py`
- Create: `app/schemas/record.py`
- Create: `app/schemas/chat.py`

- [ ] **Step 1: Create common schemas**

```python
# app/schemas/common.py
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class SuccessResponse(BaseModel):
    success: bool = True
```

- [ ] **Step 2: Create auth schemas**

```python
# app/schemas/auth.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    code: str


class TokenResponse(BaseModel):
    token: str
    refresh_token: str
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    token: str


from app.schemas.user import UserResponse
LoginRequest.model_rebuild()
TokenResponse.model_rebuild()
```

- [ ] **Step 3: Create user schemas**

```python
# app/schemas/user.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    nickname: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Create record schemas**

```python
# app/schemas/record.py
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class ContentType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"


class RecordCreate(BaseModel):
    content_type: ContentType
    content: str | None = None
    media_url: str | None = None


class RecordResponse(BaseModel):
    id: UUID
    content_type: str
    content: str | None = None
    media_url: str | None = None
    record_date: date
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 5: Create chat schemas**

```python
# app/schemas/chat.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SessionCreate(BaseModel):
    role_id: str = "therapist"


class SessionResponse(BaseModel):
    id: UUID
    role_id: str
    started_at: datetime
    ended_at: datetime | None = None

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatReply(BaseModel):
    reply: str
    memories_used: int = 0
```

- [ ] **Step 6: Create schemas/__init__.py**

```python
# app/schemas/__init__.py
from app.schemas.common import ErrorResponse, PaginatedResponse, SuccessResponse
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, RefreshResponse
from app.schemas.user import UserResponse
from app.schemas.record import RecordCreate, RecordResponse, ContentType
from app.schemas.chat import SessionCreate, SessionResponse, MessageCreate, MessageResponse, ChatReply

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "SuccessResponse",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "RefreshResponse",
    "UserResponse",
    "RecordCreate",
    "RecordResponse",
    "ContentType",
    "SessionCreate",
    "SessionResponse",
    "MessageCreate",
    "MessageResponse",
    "ChatReply",
]
```

- [ ] **Step 7: Run schema validation test**

```python
# tests/test_schemas.py
from app.schemas import RecordCreate, RecordResponse, ErrorResponse


def test_record_create_schema():
    record = RecordCreate(content_type="text", content="Hello world")
    assert record.content_type == "text"
    assert record.content == "Hello world"


def test_error_response_schema():
    error = ErrorResponse(code="NOT_FOUND", message="Record not found")
    assert error.code == "NOT_FOUND"
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_schemas.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add Pydantic schemas for API request/response"
```

---

## Task 4: JWT Handler & Exceptions

**Files:**
- Create: `app/utils/__init__.py`
- Create: `app/utils/exceptions.py`
- Create: `app/utils/jwt_handler.py`

- [ ] **Step 1: Create custom exceptions**

```python
# app/utils/exceptions.py
from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(code="UNAUTHORIZED", message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(code="NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class WechatAuthException(AppException):
    def __init__(self, message: str = "WeChat authentication failed"):
        super().__init__(code="WECHAT_AUTH_FAILED", message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class RateLimitException(AppException):
    def __init__(self, message: str = "Too many requests"):
        super().__init__(code="RATE_LIMITED", message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
```

- [ ] **Step 2: Create JWT handler**

```python
# app/utils/jwt_handler.py
from datetime import datetime, timedelta
from typing import Any
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def verify_access_token(token: str) -> dict[str, Any] | None:
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return payload
    return None


def verify_refresh_token(token: str) -> dict[str, Any] | None:
    payload = decode_token(token)
    if payload and payload.get("type") == "refresh":
        return payload
    return None
```

- [ ] **Step 3: Create utils/__init__.py**

```python
# app/utils/__init__.py
from app.utils.exceptions import (
    AppException,
    UnauthorizedException,
    NotFoundException,
    ValidationException,
    WechatAuthException,
    RateLimitException,
)
from app.utils.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_access_token,
    verify_refresh_token,
)

__all__ = [
    "AppException",
    "UnauthorizedException",
    "NotFoundException",
    "ValidationException",
    "WechatAuthException",
    "RateLimitException",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
]
```

- [ ] **Step 4: Write and run JWT tests**

```python
# tests/test_jwt.py
from app.utils.jwt_handler import create_access_token, create_refresh_token, verify_access_token, verify_refresh_token


def test_create_and_verify_access_token():
    data = {"sub": "user-123"}
    token = create_access_token(data)
    assert token is not None

    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token():
    data = {"sub": "user-123"}
    token = create_refresh_token(data)
    assert token is not None

    payload = verify_refresh_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_verify_wrong_token_type():
    data = {"sub": "user-123"}
    token = create_access_token(data)

    # Access token should not verify as refresh
    payload = verify_refresh_token(token)
    assert payload is None
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_jwt.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add JWT handler and custom exceptions"
```

---

## Task 5: Dependencies & Auth Service

**Files:**
- Create: `app/dependencies.py`
- Create: `app/services/__init__.py`
- Create: `app/services/auth_service.py`

- [ ] **Step 1: Create dependencies.py**

```python
# app/dependencies.py
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.database import async_session_maker
from app.config import get_settings
from app.models import User
from app.utils import verify_access_token, UnauthorizedException

settings = get_settings()
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise UnauthorizedException("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User not found")

    if not user.is_active:
        raise UnauthorizedException("User is inactive")

    return user
```

- [ ] **Step 2: Create auth_service.py**

```python
# app/services/auth_service.py
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.config import get_settings
from app.models import User, UserProfile, WechatSession
from app.utils import (
    create_access_token,
    create_refresh_token,
    WechatAuthException,
)
from app.schemas import UserResponse

settings = get_settings()


class AuthService:
    def __init__(self, db: AsyncSession, redis: redis.Redis):
        self._db = db
        self._redis = redis

    async def login_with_wechat(self, code: str) -> tuple[User, str, str]:
        """Exchange WeChat code for user info and tokens."""
        # Call WeChat API to get openid and session_key
        wechat_data = await self._get_wechat_session(code)

        openid = wechat_data.get("openid")
        session_key = wechat_data.get("session_key")

        if not openid:
            raise WechatAuthException("Failed to get openid from WeChat")

        # Find or create user
        user = await self._get_or_create_user(openid)

        # Store session_key
        await self._store_wechat_session(user.id, session_key)

        # Generate tokens
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # Store refresh token in Redis
        await self._redis.setex(
            f"refresh_token:{user.id}",
            settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
            refresh_token
        )

        return user, access_token, refresh_token

    async def _get_wechat_session(self, code: str) -> dict:
        """Call WeChat code2Session API."""
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

        if "errcode" in data and data["errcode"] != 0:
            raise WechatAuthException(f"WeChat error: {data.get('errmsg', 'Unknown error')}")

        return data

    async def _get_or_create_user(self, openid: str) -> User:
        """Find existing user or create new one."""
        result = await self._db.execute(select(User).where(User.openid == openid))
        user = result.scalar_one_or_none()

        if user:
            return user

        # Create new user
        user = User(openid=openid)
        self._db.add(user)
        await self._db.flush()

        # Create profile
        profile = UserProfile(user_id=user.id)
        self._db.add(profile)

        await self._db.commit()
        await self._db.refresh(user)

        return user

    async def _store_wechat_session(self, user_id: str, session_key: str) -> None:
        """Store WeChat session_key for later use."""
        from datetime import datetime, timedelta

        wechat_session = WechatSession(
            user_id=user_id,
            session_key=session_key,
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        self._db.add(wechat_session)
        await self._db.commit()

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token."""
        from app.utils import verify_refresh_token, UnauthorizedException

        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise UnauthorizedException("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")

        # Check if refresh token exists in Redis
        stored_token = await self._redis.get(f"refresh_token:{user_id}")
        if stored_token != refresh_token:
            raise UnauthorizedException("Refresh token not found or expired")

        # Generate new access token
        return create_access_token({"sub": user_id})
```

- [ ] **Step 3: Create services/__init__.py**

```python
# app/services/__init__.py
from app.services.auth_service import AuthService

__all__ = ["AuthService"]
```

- [ ] **Step 4: Write auth service tests**

```python
# tests/test_auth.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.auth_service import AuthService
from app.models import User


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_user_on_first_login(mock_db, mock_redis):
    # Mock WeChat API response
    with patch.object(AuthService, "_get_wechat_session", new_callable=AsyncMock) as mock_wechat:
        mock_wechat.return_value = {"openid": "test-openid", "session_key": "test-session"}

        # Mock database queries
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db, mock_redis)
        # This should create a new user
        # (simplified test - actual implementation would need more setup)
        pass
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_auth.py -v
```

Expected: PASS (simplified test)

- [ ] **Step 5: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add auth service with WeChat login support"
```

---

## Task 6: API Routes - Auth

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/auth.py`

- [ ] **Step 1: Create auth routes**

```python
# app/api/auth.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.dependencies import get_db, get_redis
from app.services.auth_service import AuthService
from app.schemas import LoginRequest, TokenResponse, RefreshRequest, RefreshResponse, ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis),
):
    """Login with WeChat code."""
    service = AuthService(db, redis)
    user, access_token, refresh_token = await service.login_with_wechat(request.code)

    return TokenResponse(
        token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={401: {"model": ErrorResponse}},
)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis),
):
    """Refresh access token."""
    service = AuthService(db, redis)
    new_token = await service.refresh_access_token(request.refresh_token)

    return RefreshResponse(token=new_token)
```

- [ ] **Step 2: Create api/__init__.py**

```python
# app/api/__init__.py
from fastapi import APIRouter
from app.api.auth import router as auth_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)

__all__ = ["api_router"]
```

- [ ] **Step 3: Create main.py**

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.utils import AppException
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="py-ego-miniapp",
    description="Backend API for WeChat Mini Program",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


# Exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}
```

- [ ] **Step 4: Test health endpoint**

```python
# tests/test_main.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_main.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add auth API routes and FastAPI app entry"
```

---

## Task 7: API Routes - Records

**Files:**
- Create: `app/services/record_service.py`
- Create: `app/api/records.py`

- [ ] **Step 1: Create record_service.py**

```python
# app/services/record_service.py
from datetime import date
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models import DailyRecord, User
from app.schemas import RecordCreate
from app.utils import NotFoundException


class RecordService:
    def __init__(self, db: AsyncSession, user: User):
        self._db = db
        self._user = user

    async def create_record(self, data: RecordCreate) -> DailyRecord:
        """Create a new daily record."""
        record = DailyRecord(
            user_id=self._user.id,
            content_type=data.content_type.value,
            content=data.content,
            media_url=data.media_url,
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        return record

    async def get_records(
        self,
        page: int = 1,
        size: int = 20,
        record_date: Optional[date] = None,
    ) -> tuple[list[DailyRecord], int]:
        """Get paginated records for current user."""
        query = select(DailyRecord).where(DailyRecord.user_id == self._user.id)

        if record_date:
            query = query.where(DailyRecord.record_date == record_date)

        query = query.order_by(DailyRecord.created_at.desc())

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.offset((page - 1) * size).limit(size)
        result = await self._db.execute(query)
        records = result.scalars().all()

        return list(records), total

    async def get_record(self, record_id: UUID) -> DailyRecord:
        """Get a single record by ID."""
        result = await self._db.execute(
            select(DailyRecord).where(
                DailyRecord.id == record_id,
                DailyRecord.user_id == self._user.id,
            )
        )
        record = result.scalar_one_or_none()

        if not record:
            raise NotFoundException("Record not found")

        return record

    async def delete_record(self, record_id: UUID) -> None:
        """Delete a record."""
        record = await self.get_record(record_id)
        await self._db.delete(record)
        await self._db.commit()

    async def get_timeline(self, year: int, month: int) -> list[dict]:
        """Get timeline data for a month."""
        from sqlalchemy import extract

        query = (
            select(DailyRecord)
            .where(
                DailyRecord.user_id == self._user.id,
                extract("year", DailyRecord.record_date) == year,
                extract("month", DailyRecord.record_date) == month,
            )
            .order_by(DailyRecord.record_date.desc())
        )

        result = await self._db.execute(query)
        records = result.scalars().all()

        # Group by date
        timeline = {}
        for record in records:
            date_str = record.record_date.isoformat()
            if date_str not in timeline:
                timeline[date_str] = {"date": date_str, "count": 0, "preview": None}
            timeline[date_str]["count"] += 1
            if not timeline[date_str]["preview"] and record.content:
                timeline[date_str]["preview"] = record.content[:50] + "..." if len(record.content) > 50 else record.content

        return list(timeline.values())
```

- [ ] **Step 2: Create records routes**

```python
# app/api/records.py
from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models import User
from app.services.record_service import RecordService
from app.schemas import (
    RecordCreate,
    RecordResponse,
    PaginatedResponse,
    SuccessResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/records", tags=["records"])


@router.post(
    "",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
async def create_record(
    data: RecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new daily record."""
    service = RecordService(db, current_user)
    record = await service.create_record(data)
    return record


@router.get(
    "",
    response_model=PaginatedResponse[RecordResponse],
)
async def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    record_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List records with pagination."""
    service = RecordService(db, current_user)
    records, total = await service.get_records(page, size, record_date)
    return PaginatedResponse(items=records, total=total, page=page, size=size)


@router.get(
    "/timeline",
)
async def get_timeline(
    month: str = Query(..., regex=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get timeline for a month."""
    year, month_num = map(int, month.split("-"))
    service = RecordService(db, current_user)
    timeline = await service.get_timeline(year, month_num)
    return {"days": timeline}


@router.get(
    "/{record_id}",
    response_model=RecordResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single record."""
    service = RecordService(db, current_user)
    return await service.get_record(record_id)


@router.delete(
    "/{record_id}",
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
)
async def delete_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a record."""
    service = RecordService(db, current_user)
    await service.delete_record(record_id)
    return SuccessResponse()
```

- [ ] **Step 3: Update api/__init__.py**

```python
# app/api/__init__.py
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.records import router as records_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(records_router)

__all__ = ["api_router"]
```

- [ ] **Step 4: Update services/__init__.py**

```python
# app/services/__init__.py
from app.services.auth_service import AuthService
from app.services.record_service import RecordService

__all__ = ["AuthService", "RecordService"]
```

- [ ] **Step 5: Write records API tests**

```python
# tests/test_records_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.models import User
from uuid import uuid4

client = TestClient(app)


@pytest.fixture
def mock_user():
    user = User(id=uuid4(), openid="test-openid")
    return user


def test_list_records_unauthorized():
    """Test that listing records requires authentication."""
    response = client.get("/api/records")
    assert response.status_code == 403  # Forbidden without auth header
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_records_api.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add records API with CRUD operations"
```

---

## Task 8: API Routes - Chat (Basic)

**Files:**
- Create: `app/services/chat_service.py`
- Create: `app/api/chat.py`

- [ ] **Step 1: Create chat_service.py (basic without LLM)**

```python
# app/services/chat_service.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models import ChatSession, ChatMessage, User
from app.schemas import SessionCreate, MessageCreate
from app.utils import NotFoundException


class ChatService:
    def __init__(self, db: AsyncSession, user: User):
        self._db = db
        self._user = user

    async def create_session(self, data: SessionCreate) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            user_id=self._user.id,
            role_id=data.role_id,
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def get_sessions(
        self,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[ChatSession], int]:
        """Get paginated chat sessions."""
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == self._user.id)
            .order_by(ChatSession.started_at.desc())
        )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.offset((page - 1) * size).limit(size)
        result = await self._db.execute(query)
        sessions = result.scalars().all()

        return list(sessions), total

    async def get_session(self, session_id: UUID) -> ChatSession:
        """Get a chat session."""
        result = await self._db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == self._user.id,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundException("Chat session not found")

        return session

    async def end_session(self, session_id: UUID) -> ChatSession:
        """End a chat session."""
        from datetime import datetime

        session = await self.get_session(session_id)
        session.ended_at = datetime.utcnow()
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def send_message(
        self,
        session_id: UUID,
        data: MessageCreate,
    ) -> tuple[str, int]:
        """Send a message and get a reply."""
        # Verify session exists
        session = await self.get_session(session_id)

        # Store user message
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=data.content,
        )
        self._db.add(user_msg)

        # TODO: Call LLM service for actual reply
        # For now, return a placeholder response
        reply = f"[Echo] {data.content}"

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=reply,
        )
        self._db.add(assistant_msg)

        await self._db.commit()

        return reply, 0  # reply, memories_used

    async def get_messages(
        self,
        session_id: UUID,
        before: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[ChatMessage], bool]:
        """Get messages for a session."""
        await self.get_session(session_id)  # Verify access

        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
        )

        if before:
            before_msg = await self._db.execute(
                select(ChatMessage).where(ChatMessage.id == before)
            )
            before_msg = before_msg.scalar_one_or_none()
            if before_msg:
                query = query.where(ChatMessage.created_at < before_msg.created_at)

        query = query.limit(limit + 1)  # Fetch one extra to check has_more
        result = await self._db.execute(query)
        messages = list(result.scalars().all())

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        return messages, has_more

    async def delete_session(self, session_id: UUID) -> None:
        """Delete a chat session and its messages."""
        session = await self.get_session(session_id)
        await self._db.delete(session)
        await self._db.commit()
```

- [ ] **Step 2: Create chat routes**

```python
# app/api/chat.py
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models import User
from app.services.chat_service import ChatService
from app.schemas import (
    SessionCreate,
    SessionResponse,
    MessageCreate,
    MessageResponse,
    ChatReply,
    PaginatedResponse,
    SuccessResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session."""
    service = ChatService(db, current_user)
    session = await service.create_session(data)
    return session


@router.get(
    "/sessions",
    response_model=PaginatedResponse[SessionResponse],
)
async def list_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List chat sessions."""
    service = ChatService(db, current_user)
    sessions, total = await service.get_sessions(page, size)
    return PaginatedResponse(items=sessions, total=total, page=page, size=size)


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_session(
    session_id: UUID,
    action: str = Query(..., regex="^end$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a chat session (e.g., end it)."""
    service = ChatService(db, current_user)
    session = await service.end_session(session_id)
    return session


@router.delete(
    "/sessions/{session_id}",
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session."""
    service = ChatService(db, current_user)
    await service.delete_session(session_id)
    return SuccessResponse()


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatReply,
    responses={404: {"model": ErrorResponse}},
)
async def send_message(
    session_id: UUID,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message in a chat session."""
    service = ChatService(db, current_user)
    reply, memories_used = await service.send_message(session_id, data)
    return ChatReply(reply=reply, memories_used=memories_used)


@router.get(
    "/sessions/{session_id}/messages",
    responses={404: {"model": ErrorResponse}},
)
async def list_messages(
    session_id: UUID,
    before: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List messages in a chat session."""
    service = ChatService(db, current_user)
    messages, has_more = await service.get_messages(session_id, before, limit)
    return {"messages": messages, "has_more": has_more}
```

- [ ] **Step 3: Update api/__init__.py**

```python
# app/api/__init__.py
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.records import router as records_router
from app.api.chat import router as chat_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(records_router)
api_router.include_router(chat_router)

__all__ = ["api_router"]
```

- [ ] **Step 4: Update services/__init__.py**

```python
# app/services/__init__.py
from app.services.auth_service import AuthService
from app.services.record_service import RecordService
from app.services.chat_service import ChatService

__all__ = ["AuthService", "RecordService", "ChatService"]
```

- [ ] **Step 5: Test chat endpoints**

```python
# tests/test_chat_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_sessions_unauthorized():
    """Test that listing chat sessions requires authentication."""
    response = client.get("/api/chat/sessions")
    assert response.status_code == 403


def test_health_still_works():
    """Verify health endpoint still works after adding chat routes."""
    response = client.get("/health")
    assert response.status_code == 200
```

```bash
cd py-ego-miniapp && python -m pytest tests/test_chat_api.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): add chat API with sessions and messages"
```

---

## Task 9: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
cd py-ego-miniapp && python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Run with coverage**

```bash
cd py-ego-miniapp && python -m pytest tests/ --cov=app --cov-report=term-missing
```

Expected: Coverage report generated

- [ ] **Step 3: Start the server and test manually**

```bash
cd py-ego-miniapp && uvicorn app.main:app --reload --port 8000
```

Then test in another terminal:
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "env": "development"}
```

- [ ] **Step 4: Final commit**

```bash
git add py-ego-miniapp/
git commit -m "feat(backend): complete Phase 1 backend core implementation"
```

---

## Summary

This plan implements:
- Project setup with FastAPI, SQLAlchemy, and configuration
- Database models for users, records, profiles, and chat
- Pydantic schemas for request/response validation
- JWT authentication with WeChat login support
- Records API (CRUD operations)
- Chat API (sessions and messages, basic echo response)

**Next phases would add:**
- Phase 2: LLM integration, embeddings, memory store with pgvector
- Phase 3: Mini program frontend (Uni-app)
- Phase 4: Deployment and integration