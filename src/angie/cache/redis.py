"""Redis cache client and helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis.asyncio as aioredis

from angie.config import get_settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def cache_get(key: str) -> Any | None:
    client = get_redis()
    value = await client.get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    client = get_redis()
    await client.setex(key, ttl, json.dumps(value, default=str))


async def cache_delete(key: str) -> None:
    client = get_redis()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    client = get_redis()
    keys = await client.keys(pattern)
    if keys:
        return await client.delete(*keys)
    return 0


def cached(key_prefix: str, ttl: int = 300) -> Callable:
    """Async cache decorator. Key = prefix + str(first arg)."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = f"{key_prefix}:{args[0] if args else 'default'}"
            cached_value = await cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            result = await fn(*args, **kwargs)
            if result is not None:
                await cache_set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
