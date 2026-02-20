"""Tests for angie.cache.redis."""

from unittest.mock import AsyncMock, MagicMock, patch


def _mock_settings():
    s = MagicMock()
    s.redis_url = "redis://localhost:6379/0"
    return s


def test_get_redis_singleton():
    import angie.cache.redis as redis_mod

    old_client = redis_mod._client
    redis_mod._client = None

    mock_client = MagicMock()

    with (
        patch("angie.cache.redis.get_settings", return_value=_mock_settings()),
        patch("angie.cache.redis.aioredis.from_url", return_value=mock_client),
    ):
        c1 = redis_mod.get_redis()
        c2 = redis_mod.get_redis()

    assert c1 is mock_client
    assert c2 is mock_client

    redis_mod._client = old_client


async def test_cache_get_returns_none_when_missing():
    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()
    mock_client.get.return_value = None

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        result = await redis_mod.cache_get("missing-key")

    assert result is None


async def test_cache_get_returns_value():
    import json

    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()
    mock_client.get.return_value = json.dumps({"foo": "bar"})

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        result = await redis_mod.cache_get("my-key")

    assert result == {"foo": "bar"}


async def test_cache_set():
    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        await redis_mod.cache_set("my-key", {"value": 42}, ttl=60)

    mock_client.setex.assert_called_once()
    args = mock_client.setex.call_args[0]
    assert args[0] == "my-key"
    assert args[1] == 60


async def test_cache_delete():
    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        await redis_mod.cache_delete("my-key")

    mock_client.delete.assert_called_once_with("my-key")


async def test_cache_delete_pattern_with_keys():
    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()
    mock_client.keys.return_value = ["prefix:1", "prefix:2"]
    mock_client.delete.return_value = 2

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        count = await redis_mod.cache_delete_pattern("prefix:*")

    assert count == 2
    mock_client.delete.assert_called_once_with("prefix:1", "prefix:2")


async def test_cache_delete_pattern_no_keys():
    import angie.cache.redis as redis_mod

    mock_client = AsyncMock()
    mock_client.keys.return_value = []

    with patch.object(redis_mod, "get_redis", return_value=mock_client):
        count = await redis_mod.cache_delete_pattern("prefix:*")

    assert count == 0
    mock_client.delete.assert_not_called()


async def test_cached_decorator_cache_miss():
    import angie.cache.redis as redis_mod

    mock_fn = AsyncMock(return_value={"data": "fresh"})
    decorated = redis_mod.cached("test-prefix", ttl=30)(mock_fn)

    with (
        patch.object(redis_mod, "cache_get", AsyncMock(return_value=None)),
        patch.object(redis_mod, "cache_set", AsyncMock()),
    ):
        result = await decorated("arg1")

    assert result == {"data": "fresh"}
    mock_fn.assert_called_once_with("arg1")


async def test_cached_decorator_cache_hit():
    import angie.cache.redis as redis_mod

    mock_fn = AsyncMock(return_value={"data": "fresh"})
    decorated = redis_mod.cached("test-prefix", ttl=30)(mock_fn)

    with (
        patch.object(redis_mod, "cache_get", AsyncMock(return_value={"data": "cached"})),
        patch.object(redis_mod, "cache_set", AsyncMock()) as mock_set,
    ):
        result = await decorated("arg1")

    assert result == {"data": "cached"}
    mock_fn.assert_not_called()
    mock_set.assert_not_called()


async def test_cached_decorator_none_result_not_cached():
    import angie.cache.redis as redis_mod

    mock_fn = AsyncMock(return_value=None)
    decorated = redis_mod.cached("test-prefix")(mock_fn)

    with (
        patch.object(redis_mod, "cache_get", AsyncMock(return_value=None)),
        patch.object(redis_mod, "cache_set", AsyncMock()) as mock_set,
    ):
        result = await decorated("arg1")

    assert result is None
    mock_set.assert_not_called()


async def test_cached_decorator_no_args():
    import angie.cache.redis as redis_mod

    mock_fn = AsyncMock(return_value="result")
    decorated = redis_mod.cached("test-prefix")(mock_fn)

    with (
        patch.object(redis_mod, "cache_get", AsyncMock(return_value=None)),
        patch.object(redis_mod, "cache_set", AsyncMock()),
    ):
        result = await decorated()

    # Should use 'default' as key suffix
    assert result == "result"
