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


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_relevant_keyword(mock_pm, mock_gs):
    """Agent responds when the user message matches its capabilities."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class WeatherDummy(BaseAgent):
        name = "Weather"
        slug = "weather"
        description = "test"
        capabilities = ["weather", "forecast", "temperature"]

        async def execute(self, task):
            return {}

    agent = WeatherDummy()
    task = {
        "input_data": {
            "intent": "What's the weather like in NYC?",
            "parameters": {"auto_notify": True},
        }
    }
    assert await agent.should_respond(task) is True


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_irrelevant_message(mock_pm, mock_gs):
    """Agent declines when the user message doesn't match capabilities."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class WeatherDummy(BaseAgent):
        name = "Weather"
        slug = "weather"
        description = "test"
        capabilities = ["weather", "forecast", "temperature"]

        async def execute(self, task):
            return {}

    agent = WeatherDummy()
    task = {
        "input_data": {
            "intent": "remind me to cut the grass tomorrow",
            "parameters": {"auto_notify": True},
        }
    }
    assert await agent.should_respond(task) is False


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_no_auto_notify(mock_pm, mock_gs):
    """Agent declines when auto_notify is not set."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"
        capabilities = ["anything"]

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    task = {"input_data": {"intent": "anything goes", "parameters": {}}}
    assert await agent.should_respond(task) is False


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_no_capabilities(mock_pm, mock_gs):
    """Agent with no capabilities always declines auto_notify."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class NoCaps(BaseAgent):
        name = "NoCaps"
        slug = "nocaps"
        description = "test"
        capabilities = []

        async def execute(self, task):
            return {}

    agent = NoCaps()
    task = {
        "input_data": {
            "intent": "do something",
            "parameters": {"auto_notify": True},
        }
    }
    assert await agent.should_respond(task) is False


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_context_relevance(mock_pm, mock_gs):
    """Agent responds when recent conversation history matches capabilities."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class WeatherDummy(BaseAgent):
        name = "Weather"
        slug = "weather"
        description = "test"
        capabilities = ["weather", "forecast"]

        async def execute(self, task):
            return {}

    agent = WeatherDummy()
    # Current message doesn't mention weather, but recent history does
    task = {
        "input_data": {
            "intent": "thanks, what about tomorrow?",
            "conversation_id": "conv-123",
            "parameters": {"auto_notify": True},
        }
    }
    # Mock get_conversation_history to return recent weather context
    history = [
        {"role": "user", "content": "What's the weather forecast for NYC?", "agent_slug": ""},
        {"role": "ASSISTANT", "content": "It's 72F and sunny.", "agent_slug": "weather"},
    ]
    with patch.object(
        agent, "get_conversation_history", new_callable=AsyncMock, return_value=history
    ):
        assert await agent.should_respond(task) is True


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_should_respond_context_irrelevant(mock_pm, mock_gs):
    """Agent declines when both message and history are irrelevant."""
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class WeatherDummy(BaseAgent):
        name = "Weather"
        slug = "weather"
        description = "test"
        capabilities = ["weather", "forecast"]

        async def execute(self, task):
            return {}

    agent = WeatherDummy()
    task = {
        "input_data": {
            "intent": "remind me to cut the grass",
            "conversation_id": "conv-123",
            "parameters": {"auto_notify": True},
        }
    }
    history = [
        {"role": "user", "content": "check my github PRs", "agent_slug": ""},
        {"role": "ASSISTANT", "content": "You have 3 open PRs.", "agent_slug": "github"},
    ]
    with patch.object(
        agent, "get_conversation_history", new_callable=AsyncMock, return_value=history
    ):
        assert await agent.should_respond(task) is False


# ── _notify_subscribed_agents exclusion tests ────────────────────────────────


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_notify_excludes_dispatched_agents(mock_gs):
    """Agents dispatched via dispatch_task tool are excluded from auto-notify."""
    mock_gs.return_value = MagicMock()

    with (
        patch(
            "angie.core.conv_subscriptions.get_subscribed_agents",
            new_callable=AsyncMock,
            return_value={"github", "weather"},
        ),
        patch(
            "angie.core.conv_subscriptions.check_cooldown",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "angie.core.conv_subscriptions.set_cooldown",
            new_callable=AsyncMock,
        ),
        patch(
            "angie.core.intent.dispatch_task",
            new_callable=AsyncMock,
        ) as mock_dispatch,
    ):
        from angie.api.routers.chat import _notify_subscribed_agents

        # github was dispatched by the LLM, so only weather should be notified
        await _notify_subscribed_agents(
            conversation_id="conv-1",
            user_id="user-1",
            user_message="check my PRs",
            mentioned_slugs={"github"},
        )

        # Only weather should have been dispatched (github excluded)
        assert mock_dispatch.call_count == 1
        dispatch_call = mock_dispatch.call_args
        assert dispatch_call.kwargs["agent_slug"] == "weather"


@pytest.mark.asyncio
@patch("angie.config.get_settings")
async def test_notify_excludes_both_mentioned_and_dispatched(mock_gs):
    """Both @-mentioned and LLM-dispatched agents are excluded from auto-notify."""
    mock_gs.return_value = MagicMock()

    with (
        patch(
            "angie.core.conv_subscriptions.get_subscribed_agents",
            new_callable=AsyncMock,
            return_value={"github", "weather", "web"},
        ),
        patch(
            "angie.core.conv_subscriptions.check_cooldown",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "angie.core.conv_subscriptions.set_cooldown",
            new_callable=AsyncMock,
        ),
        patch(
            "angie.core.intent.dispatch_task",
            new_callable=AsyncMock,
        ) as mock_dispatch,
    ):
        from angie.api.routers.chat import _notify_subscribed_agents

        # github @-mentioned, web dispatched by LLM — only weather notified
        await _notify_subscribed_agents(
            conversation_id="conv-1",
            user_id="user-1",
            user_message="search the web for github alternatives",
            mentioned_slugs={"github", "web"},
        )

        assert mock_dispatch.call_count == 1
        dispatch_call = mock_dispatch.call_args
        assert dispatch_call.kwargs["agent_slug"] == "weather"
