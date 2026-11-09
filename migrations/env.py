"""Run Alembic migrations with an async PostgreSQL connection."""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from ratemypic.database import get_database_url
from ratemypic.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations(connection) -> None:
    """Run migrations using the connection supplied by async SQLAlchemy."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async connection and hand it to Alembic."""
    engine = create_async_engine(get_database_url(), poolclass=pool.NullPool)

    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


def run_migrations_offline() -> None:
    """Print migration SQL without connecting to PostgreSQL."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())