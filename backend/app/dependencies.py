"""
CloudPulse — Reusable FastAPI Dependencies

Centralising deps here means every router imports from one place,
making it easy to swap implementations (e.g. mock DB in tests).
"""
from fastapi import Depends, Query, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from typing import Annotated


# ── Type aliases (Python 3.10+ style) ────────────────────────────────────────

DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginationParams:
    """
    Standard offset/limit pagination injected via query params.
    Usage: params: PaginationParams = Depends()
    """
    def __init__(
        self,
        page: int  = Query(default=1,   ge=1,    description="Page number (1-based)"),
        size: int  = Query(default=50,  ge=1, le=500, description="Items per page"),
    ):
        self.offset = (page - 1) * size
        self.limit  = size
        self.page   = page
        self.size   = size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]


# ── Optional agent API-key guard ─────────────────────────────────────────────

async def verify_agent_key(
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")
) -> None:
    """
    If AGENT_API_KEY is set in .env, the monitoring agent must send it as
    the 'X-Agent-Key' header on POST /api/metrics/.
    Leave AGENT_API_KEY unset (or empty) to skip auth in development.
    """
    expected = getattr(settings, "AGENT_API_KEY", None)
    if not expected:          # auth disabled
        return
    if x_agent_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Agent-Key header.",
        )


AgentAuth = Annotated[None, Depends(verify_agent_key)]
