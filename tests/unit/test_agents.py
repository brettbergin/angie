"""Unit tests for the agent registry."""

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
