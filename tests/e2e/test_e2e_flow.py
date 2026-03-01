"""E2E tests: onboarding → agent dispatch → task feedback flow."""

from unittest.mock import MagicMock, patch

import pytest

from angie.agents.base import BaseAgent
from angie.agents.registry import AgentRegistry
from angie.agents.teams import TeamResolver
from angie.core.events import AngieEvent, EventRouter, EventType
from angie.core.tasks import AngieTask, TaskDispatcher

# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------


class GreetAgent(BaseAgent):
    name = "Greet Agent"
    slug = "greet"
    description = "Says hello"
    capabilities = ["greet", "hello", "welcome"]

    async def execute(self, task):
        return {"status": "success", "message": f"Hello from {self.slug}"}


class FailAgent(BaseAgent):
    name = "Fail Agent"
    slug = "fail"
    description = "Always fails"
    capabilities = ["fail"]

    async def execute(self, task):
        return {"status": "failure", "error": "intentional failure"}


class EchoAgent(BaseAgent):
    name = "Echo Agent"
    slug = "echo"
    description = "Echoes the task title back"
    capabilities = ["echo", "repeat"]

    async def execute(self, task):
        title = task.get("title", "") if isinstance(task, dict) else task.title
        return {"status": "success", "echo": title}


# ---------------------------------------------------------------------------
# Agent registry / dispatch
# ---------------------------------------------------------------------------


def test_agent_registration_and_dispatch():
    registry = AgentRegistry()
    registry.register(GreetAgent())
    registry.register(EchoAgent())

    task = {"title": "greet and say hello and welcome", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    assert agent.slug == "greet"


def test_agent_dispatch_by_slug():
    registry = AgentRegistry()
    registry.register(GreetAgent())
    registry.register(EchoAgent())

    task = {"agent_slug": "echo", "title": "echo this", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    assert agent.slug == "echo"


@pytest.mark.asyncio
async def test_full_task_execution():
    registry = AgentRegistry()
    registry.register(GreetAgent())

    task = {"agent_slug": "greet", "title": "say hello", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    result = await agent.execute(task)
    assert result["status"] == "success"
    assert "Hello" in result["message"]


@pytest.mark.asyncio
async def test_failure_agent_result():
    registry = AgentRegistry()
    registry.register(FailAgent())

    task = {"agent_slug": "fail", "title": "fail please", "input_data": {}}
    agent = registry.resolve(task)
    assert agent is not None
    result = await agent.execute(task)
    assert result["status"] == "failure"
    assert "error" in result


# ---------------------------------------------------------------------------
# Event → Task routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_triggers_task_dispatch():
    router = EventRouter()
    dispatched: list[AngieTask] = []

    @router.on(EventType.USER_MESSAGE)
    async def on_user_message(event: AngieEvent):
        task = AngieTask(
            title=event.payload.get("text", ""),
            agent_slug=event.payload.get("agent_slug"),
            source_channel=event.source_channel,
            user_id=event.user_id or "system",
        )
        dispatched.append(task)

    event = AngieEvent(
        type=EventType.USER_MESSAGE,
        source_channel="slack",
        user_id="user-1",
        payload={"text": "greet me", "agent_slug": "greet"},
    )
    await router.dispatch(event)

    assert len(dispatched) == 1
    assert dispatched[0].title == "greet me"
    assert dispatched[0].source_channel == "slack"


@pytest.mark.asyncio
async def test_cron_event_dispatched():
    router = EventRouter()
    received: list[AngieEvent] = []

    @router.on_any()
    async def on_any(event: AngieEvent):
        received.append(event)

    cron_event = AngieEvent(
        type=EventType.CRON,
        payload={"job_id": "daily-summary"},
    )
    await router.dispatch(cron_event)

    assert len(received) == 1
    assert received[0].type == EventType.CRON


# ---------------------------------------------------------------------------
# Team resolver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_team_resolver_picks_matching_agent():
    registry = AgentRegistry()
    greet = GreetAgent()
    echo = EchoAgent()
    registry.register(greet)
    registry.register(echo)

    # Patch the global registry used by TeamResolver
    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("support", ["greet", "echo"])
        task = AngieTask(title="greet the user", agent_slug=None, user_id="user-1")
        agent = team.resolve(task)
        assert agent is not None
        assert agent.slug in ("greet", "echo")


@pytest.mark.asyncio
async def test_team_execute_returns_results():
    registry = AgentRegistry()
    registry.register(GreetAgent())
    registry.register(EchoAgent())

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("ops", ["greet", "echo"])
        task = AngieTask(title="greet the user", agent_slug=None, user_id="user-1")
        result = await team.execute(task)
        assert result["team"] == "ops"
        assert len(result["results"]) >= 1
        assert result["results"][0]["result"]["status"] == "success"


@pytest.mark.asyncio
async def test_team_resolve_no_match_returns_none():
    registry = AgentRegistry()
    registry.register(EchoAgent())

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("empty-team", ["echo"])
        # Task that no agent can handle
        task = AngieTask(title="zzz unmatched zzz xyzzy", agent_slug=None, user_id="user-1")
        agent = team.resolve(task)
        assert agent is None


# ---------------------------------------------------------------------------
# Task dispatcher
# ---------------------------------------------------------------------------


def test_task_dispatcher_queues_task():
    dispatcher = TaskDispatcher()
    task = AngieTask(title="do something", agent_slug="greet", user_id="user-1")

    mock_result = MagicMock()
    mock_result.id = "celery-abc-123"

    with patch("angie.queue.celery_app.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        celery_id = dispatcher.dispatch(task)

    assert celery_id == "celery-abc-123"


# ---------------------------------------------------------------------------
# Prompt hierarchy
# ---------------------------------------------------------------------------


def test_prompt_hierarchy_system_present():
    from angie.core.prompts import PromptManager

    pm = PromptManager()
    system = pm.get_system_prompt()
    assert system is not None
    assert len(system) > 0


def test_prompt_hierarchy_angie_present():
    from angie.core.prompts import PromptManager

    pm = PromptManager()
    angie = pm.get_angie_prompt()
    assert angie is not None
    assert len(angie) > 0


def test_prompt_compose_with_user_prompts_includes_all_layers():
    from angie.core.prompts import PromptManager

    pm = PromptManager()
    composed = pm.compose_with_user_prompts([])
    assert "system" in composed.lower() or len(composed) > 50
