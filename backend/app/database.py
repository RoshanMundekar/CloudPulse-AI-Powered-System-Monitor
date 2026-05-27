"""
CloudPulse — Async Database Engine

Key design decisions:
- pool_pre_ping=True  → validates connections before use (avoids stale-connection errors)
- pool_recycle=1800   → replace connections after 30 min (PostgreSQL idle timeout safety)
- pool_size / max_overflow tuned for ~20 concurrent requests
- expire_on_commit=False → ORM objects stay usable after commit without extra SELECT
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import event, text
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.config import settings
import logging

log = logging.getLogger("cloudpulse.db")


# ── Engine ────────────────────────────────────────────────────────────────────

def _make_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,           # SQL logging in dev
        pool_size=10,                  # persistent connections kept open
        max_overflow=20,               # extra connections allowed under load
        pool_pre_ping=True,            # test connection health before use
        pool_recycle=1800,             # replace connections every 30 min
        pool_timeout=30,               # wait up to 30 s for a free connection
    )


engine = _make_engine()

# ── Session factory ────────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # don't reload ORM objects after commit
    autoflush=False,          # explicit flushes only (avoids surprise queries)
)


# ── ORM base ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields one async DB session per request.
    Rolls back on exception, always closes the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle helpers ──────────────────────────────────────────────────────────

async def create_tables() -> None:
    """Create all mapped tables if they don't exist (dev / first-run helper)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables verified/created.")


async def dispose_engine() -> None:
    """Gracefully close all pool connections (call on app shutdown)."""
    await engine.dispose()
    log.info("Database engine disposed.")


async def check_db_health() -> dict:
    """
    Lightweight health probe — runs SELECT 1 to confirm DB reachability.
    Returns a dict so it can be embedded in /health responses.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        log.error(f"DB health check failed: {exc}")
        return {"status": "error", "detail": str(exc)}
