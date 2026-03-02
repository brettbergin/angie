"""Unit tests for the agent registry and base agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from angie.agents.base import BaseAgent
from angie.agents.registry import AgentRegistry


class MockAgent(BaseAgent):
    name = "Mock Agent"
    slug = "mock"
    description = "A mock agent for testing"
    capabilities = ["mock", "test"]

    async def execute(self, task):
        return {"status": "ok", "agent": self.slug}


def test_registry_register_and_get():
    registry = AgentRegistry()
    registry.register(MockAgent())
    agent = registry.get("mock")
    assert agent is not None
    assert agent.slug == "mock"


def test_registry_get_missing_returns_none():
    registry = AgentRegistry()
    assert registry.get("nonexistent") is None


def test_registry_resolve_by_slug():
    registry = AgentRegistry()
    registry.register(MockAgent())
    task = {"agent_slug": "mock", "title": "do something", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    assert agent.slug == "mock"


def test_registry_resolve_by_capability():
    registry = AgentRegistry()
    registry.register(MockAgent())
    # Both capabilities ("mock" and "test") must appear for confidence >= 0.5
    task = {"title": "run a mock test operation", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    assert agent.slug == "mock"


def test_registry_resolve_no_match():
    registry = AgentRegistry()
    registry.register(MockAgent())
    task = {"title": "do something completely unrelated", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is None


def test_registry_list_all():
    registry = AgentRegistry()
    registry.register(MockAgent())
    agents = registry.list_all()
    assert any(a.slug == "mock" for a in agents)


@pytest.mark.asyncio
async def test_agent_execute():
    agent = MockAgent()
    result = await agent.execute({"title": "test", "input_data": {}})
    assert result["status"] == "ok"
    assert result["agent"] == "mock"


def test_agent_can_handle_by_slug():
    agent = MockAgent()
    assert agent.can_handle({"agent_slug": "mock"}) is True
    assert agent.can_handle({"agent_slug": "other"}) is False


def test_agent_can_handle_by_capability():
    agent = MockAgent()
    assert agent.can_handle({"title": "run a mock test"}) is True
    assert agent.can_handle({"title": "unrelated task"}) is False


# ── BaseAgent: build_pydantic_agent / _get_agent ─────────────────────────────


def test_build_pydantic_agent_returns_agent():
    """Covers build_pydantic_agent (line 66-68)."""
    agent = MockAgent()
    pa = agent.build_pydantic_agent()
    assert pa is not None


def test_get_agent_caches_instance():
    """Covers _get_agent caching branch (lines 72-74)."""
    agent = MockAgent()
    first = agent._get_agent()
    second = agent._get_agent()
    assert first is second


# ── BaseAgent: _run_with_tracking ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_with_tracking():
    """Covers _run_with_tracking and token recording."""
    agent = MockAgent()

    mock_result = MagicMock()
    mock_result.output = "hello"
    mock_usage = MagicMock()
    mock_usage.input_tokens = 10
    mock_usage.output_tokens = 5
    mock_usage.total_tokens = 15
    mock_usage.requests = 1
    mock_result.usage.return_value = mock_usage

    mock_pa = AsyncMock()
    mock_pa.run = AsyncMock(return_value=mock_result)
    agent._pydantic_agent = mock_pa

    with patch("angie.core.token_usage.record_usage_fire_and_forget") as mock_fire:
        result = await agent._run_with_tracking(
            "test prompt",
            model="test-model",
            user_id="u1",
            task_id="t1",
            conversation_id="c1",
        )

    assert result is mock_result
    mock_fire.assert_called_once()
    call_kwargs = mock_fire.call_args[1]
    assert call_kwargs["user_id"] == "u1"
    assert call_kwargs["agent_slug"] == "mock"
    assert call_kwargs["source"] == "agent_execute"


# ── BaseAgent: get_credentials ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_credentials_no_user_id():
    """Covers get_credentials early return when user_id is None (line 382-383)."""
    agent = MockAgent()
    result = await agent.get_credentials(None, "github")
    assert result is None


@pytest.mark.asyncio
async def test_get_credentials_success():
    """Covers the happy path of get_credentials (lines 384-390)."""
    agent = MockAgent()

    mock_conn = MagicMock()
    mock_conn.credentials_encrypted = b"encrypted-data"

    with (
        patch(
            "angie.core.connections.get_connection", new_callable=AsyncMock, return_value=mock_conn
        ),
        patch("angie.core.crypto.decrypt_json", return_value={"token": "abc123"}),
    ):
        result = await agent.get_credentials("user-1", "github")

    assert result == {"token": "abc123"}


@pytest.mark.asyncio
async def test_get_credentials_handles_exception():
    """Covers the exception handler in get_credentials (lines 391-393)."""
    agent = MockAgent()

    with patch(
        "angie.core.connections.get_connection",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB error"),
    ):
        result = await agent.get_credentials("user-1", "github")

    assert result is None


# ── BaseAgent: should_respond ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_should_respond_no_auto_notify():
    """should_respond returns False when auto_notify is missing."""
    agent = MockAgent()
    task = {"input_data": {"parameters": {}}}
    assert await agent.should_respond(task) is False


@pytest.mark.asyncio
async def test_should_respond_no_intent():
    """Covers the _extract_intent returning None branch (line 218-220)."""
    agent = MockAgent()
    task = {"input_data": {"parameters": {"auto_notify": True}}}
    # _extract_intent will return None since there's no title or message
    assert await agent.should_respond(task) is False
