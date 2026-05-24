from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for FastAPI dependencies."""

    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all database tables."""

    from app import models  # noqa: F401  # Ensure models are registered.

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_schema_columns)


def _ensure_schema_columns(connection) -> None:
    """Backfill new columns when an older local database already exists."""

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    def has_column(table_name: str, column_name: str) -> bool:
        if table_name not in existing_tables:
            return False
        return any(column["name"] == column_name for column in inspector.get_columns(table_name))

    statements: list[str] = []
    if not has_column("approval_requests", "decided_by_agent_id"):
        statements.append(
            """
            ALTER TABLE approval_requests
            ADD COLUMN decided_by_agent_id UUID
            """
        )
        statements.append(
            """
            ALTER TABLE approval_requests
            ADD CONSTRAINT fk_approval_requests_decided_by_agent_id
            FOREIGN KEY (decided_by_agent_id) REFERENCES agents (id) ON DELETE SET NULL
            """
        )

    if not has_column("audit_logs", "event_hash"):
        statements.append(
            """
            ALTER TABLE audit_logs
            ADD COLUMN event_hash VARCHAR(64)
            """
        )
    if not has_column("audit_logs", "previous_event_hash"):
        statements.append(
            """
            ALTER TABLE audit_logs
            ADD COLUMN previous_event_hash VARCHAR(64)
            """
        )

    for statement in statements:
        connection.execute(text(statement))


async def dispose_db() -> None:
    """Close engine resources on shutdown."""

    await engine.dispose()
