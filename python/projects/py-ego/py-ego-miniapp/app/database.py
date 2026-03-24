"""SQLAlchemy async database configuration."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Dependency that provides an async database session.

    Yields:
        AsyncSession: SQLAlchemy async session for database operations.

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
        ```
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()