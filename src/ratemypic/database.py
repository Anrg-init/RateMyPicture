"""Async PostgreSQL connection and session helpers."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ratemypic.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> URL:
    """Read and validate the PostgreSQL URL from the .env file."""
    load_dotenv()

    # In tests, TEST_DATABASE_URL can override DATABASE_URL
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing. Add it to your .env file.")

    url = make_url(database_url)
    supported_drivers = {
        "postgres",
        "postgresql",
        "postgresql+asyncpg",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }
    if url.drivername not in supported_drivers:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")

    # asyncpg is the PostgreSQL driver used by this asynchronous project.
    return url.set(drivername="postgresql+asyncpg")


def get_engine() -> AsyncEngine:
    """Return the one shared async engine for this application process."""
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={"timeout": 10},
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared factory used to open async database sessions."""
    global _session_factory

    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )

    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Open a transaction; commit on success and roll back on errors."""
    async with get_session_factory().begin() as session:
        yield session


async def test_connection() -> None:
    """Run a small query to check that PostgreSQL is reachable."""
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))

    print("PostgreSQL connection is working.")


async def create_tables() -> None:
    """Create tables for local development; deployed changes should use migrations."""
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """Close pooled connections during application shutdown."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None