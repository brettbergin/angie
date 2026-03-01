"""Tests for conversation subscription system."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


@pytest.fixture
def mock_redis():
    """Create a mock async Redis client."""
    client = AsyncMock()
    client.scard = AsyncMock(return_value=0)
    client.sismember = AsyncMock(return_value=False)
    client.sadd = AsyncMock()
    client.srem = AsyncMock()
    client.expire = AsyncMock()
    client.smembers = AsyncMock(return_value=set())
    client.exists = AsyncMock(return_value=0)
    client.setex = AsyncMock()
    return client


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_subscribe_agent(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import subscribe_agent

        result = await subscribe_agent("conv-1", "weather")
        assert result is True
        mock_redis.sadd.assert_called_once_with("angie:conv_subs:conv-1", "weather")
        mock_redis.expire.assert_called_once()


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_subscribe_agent_cap_reached(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.scard = AsyncMock(return_value=5)
    mock_redis.sismember = AsyncMock(return_value=False)
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import subscribe_agent

        result = await subscribe_agent("conv-1", "new-agent")
        assert result is False
        mock_redis.sadd.assert_not_called()


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_subscribe_agent_already_subscribed_at_cap(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.scard = AsyncMock(return_value=5)
    mock_redis.sismember = AsyncMock(return_value=True)
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import subscribe_agent

        result = await subscribe_agent("conv-1", "weather")
        assert result is True


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_unsubscribe_agent(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import unsubscribe_agent

        await unsubscribe_agent("conv-1", "weather")
        mock_redis.srem.assert_called_once_with("angie:conv_subs:conv-1", "weather")


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_get_subscribed_agents(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.smembers = AsyncMock(return_value={"weather", "github"})
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import get_subscribed_agents

        result = await get_subscribed_agents("conv-1")
        assert result == {"weather", "github"}


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_get_subscribed_agents_redis_error(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.smembers = AsyncMock(side_effect=Exception("Redis down"))
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import get_subscribed_agents

        result = await get_subscribed_agents("conv-1")
        assert result == set()


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_check_cooldown_not_in_cooldown(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.exists = AsyncMock(return_value=0)
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import check_cooldown

        result = await check_cooldown("conv-1", "weather")
        assert result is False


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_check_cooldown_in_cooldown(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    mock_redis.exists = AsyncMock(return_value=1)
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import check_cooldown

        result = await check_cooldown("conv-1", "weather")
        assert result is True


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_set_cooldown(mock_gs, mock_redis):
    mock_gs.return_value = MagicMock()
    with patch("angie.core.conv_subscriptions.get_redis", return_value=mock_redis):
        from angie.core.conv_subscriptions import set_cooldown

        await set_cooldown("conv-1", "weather")
        mock_redis.setex.assert_called_once_with("angie:auto_cooldown:conv-1:weather", 30, "1")


# ── should_respond tests ─────────────────────────────────────────────────────


@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
def test_should_respond_auto_notify_true(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    task = {"input_data": {"parameters": {"auto_notify": True}}}
    assert agent.should_respond(task) is True


@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
def test_should_respond_no_auto_notify(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    task = {"input_data": {"parameters": {}}}
    assert agent.should_respond(task) is False
