from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Global engine — used by FastAPI (single process, single event loop)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    """FastAPI dependency for DB sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_isolated_session():
    """
    Create a fully isolated async session with its own engine.

    Used by Celery tasks where each invocation runs in a fresh event loop
    inside a forked worker process. The global engine cannot be reused
    because asyncpg connections are bound to the event loop that created them.
    """
    iso_engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=2,
        max_overflow=3,
    )
    iso_factory = async_sessionmaker(
        iso_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with iso_factory() as session:
        try:
            yield session
        finally:
            await session.close()
    await iso_engine.dispose()
