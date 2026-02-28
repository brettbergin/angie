"""Detailed health endpoint — component-level status for the Angie system."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_start_time = time.monotonic()


@router.get("/api/v1/health")
async def health_check():
    """Return detailed health status for all Angie components."""
    result = {
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "channels": {},
        "db": "unknown",
        "redis": "unknown",
        "active_agents": [],
    }

    # Check channels
    try:
        from angie.channels.base import get_channel_manager

        mgr = get_channel_manager()
        for name, channel in mgr._channels.items():
            try:
                healthy = await channel.health_check()
                result["channels"][name] = "connected" if healthy else "unhealthy"
            except Exception:
                result["channels"][name] = "error"
    except Exception:
        pass

    # Check DB
    try:
        from angie.db.session import get_session_factory

        async with get_session_factory()() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        result["db"] = "connected"
    except Exception:
        result["db"] = "disconnected"

    # Check Redis
    try:
        import redis

        from angie.config import get_settings

        settings = get_settings()
        r = redis.from_url(settings.redis_url)
        r.ping()
        r.close()
        result["redis"] = "connected"
    except Exception:
        result["redis"] = "disconnected"

    # List active agents
    try:
        from angie.agents.registry import get_registry

        registry = get_registry()
        result["active_agents"] = [a.slug for a in registry.list_all()]
    except Exception:
        pass

    # Set overall status
    if result["db"] == "disconnected":
        result["status"] = "degraded"

    return result
