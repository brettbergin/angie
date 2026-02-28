"""Health endpoint — public liveness check for the Angie system.

Returns only non-sensitive status information (no internal component details,
agent names, or infrastructure topology) so it is safe to expose without auth.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.monotonic()


@router.get("/api/v1/health")
async def health_check():
    """Return a minimal health status (safe for unauthenticated access)."""
    from sqlalchemy import text

    db_ok = False
    redis_ok = False

    # Check DB
    try:
        from angie.db.session import get_session_factory

        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check Redis
    try:
        import redis

        from angie.config import get_settings

        settings = get_settings()
        r = redis.from_url(settings.redis_url)
        r.ping()
        r.close()
        redis_ok = True
    except Exception:
        pass

    status = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
    }
