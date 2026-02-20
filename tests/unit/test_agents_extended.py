"""Extended tests for agents: BaseAgent, teams, registry, system agents."""

from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from angie.agents.base import BaseAgent
from angie.agents.registry import AgentRegistry, agent
from angie.agents.teams import TeamResolver, all_teams, get_team, register_team
from angie.core.tasks import AngieTask

# ── Concrete test agent ───────────────────────────────────────────────────────


class DummyAgent(BaseAgent):
    name: ClassVar[str] = "Dummy"
    slug: ClassVar[str] = "dummy"
    description: ClassVar[str] = "A test agent"
    capabilities: ClassVar[list[str]] = ["dummy", "test"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "agent": self.slug}


class FailingAgent(BaseAgent):
    name: ClassVar[str] = "Failing Agent"
    slug: ClassVar[str] = "failing"
    description: ClassVar[str] = "Always fails"
    capabilities: ClassVar[list[str]] = ["fail"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"status": "failure", "agent": self.slug}


# ── BaseAgent tests ───────────────────────────────────────────────────────────


def test_base_agent_can_handle_by_slug():
    agent_obj = DummyAgent()
    assert agent_obj.can_handle({"agent_slug": "dummy"}) is True
    assert agent_obj.can_handle({"agent_slug": "other"}) is False


def test_base_agent_can_handle_by_capability():
    agent_obj = DummyAgent()
    assert agent_obj.can_handle({"title": "run a dummy task"}) is True
    assert agent_obj.can_handle({"title": "do something else"}) is False


def test_base_agent_repr():
    agent_obj = DummyAgent()
    assert "DummyAgent" in repr(agent_obj)
    assert "dummy" in repr(agent_obj)


def test_base_agent_get_system_prompt():
    agent_obj = DummyAgent()
    mock_pm = MagicMock()
    mock_pm.compose_for_agent.return_value = "system prompt text"

    with patch.object(agent_obj, "prompt_manager", mock_pm):
        prompt = agent_obj.get_system_prompt()

    assert prompt == "system prompt text"
    mock_pm.compose_for_agent.assert_called_once_with("dummy")


async def test_base_agent_ask_llm():
    agent_obj = DummyAgent()

    mock_result = MagicMock()
    mock_result.output = "LLM response"
    mock_ai_agent = AsyncMock()
    mock_ai_agent.run.return_value = mock_result

    with (
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch("pydantic_ai.Agent", return_value=mock_ai_agent),
    ):
        response = await agent_obj.ask_llm("Hello", system="You are a bot")

    assert response == "LLM response"


async def test_base_agent_ask_llm_with_auto_system_prompt():
    agent_obj = DummyAgent()

    mock_pm = MagicMock()
    mock_pm.compose_for_agent.return_value = "auto system prompt"

    mock_result = MagicMock()
    mock_result.output = "response"
    mock_ai_agent = AsyncMock()
    mock_ai_agent.run.return_value = mock_result

    with (
        patch.object(agent_obj, "prompt_manager", mock_pm),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch("pydantic_ai.Agent", return_value=mock_ai_agent),
    ):
        response = await agent_obj.ask_llm("Hello")

    assert response == "response"


async def test_base_agent_ask_llm_raises():
    agent_obj = DummyAgent()

    mock_ai_agent = AsyncMock()
    mock_ai_agent.run.side_effect = RuntimeError("LLM error")

    with (
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch("pydantic_ai.Agent", return_value=mock_ai_agent),
    ):
        with pytest.raises(RuntimeError, match="LLM error"):
            await agent_obj.ask_llm("Hello", system="sys")


async def test_base_agent_execute():
    agent_obj = DummyAgent()
    result = await agent_obj.execute({"title": "test"})
    assert result["status"] == "ok"


# ── AgentRegistry extended ────────────────────────────────────────────────────


def test_registry_load_all():
    registry = AgentRegistry()
    with patch("angie.agents.registry.importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.__dict__ = {}

        class FakeAgent(BaseAgent):
            name = "Fake"
            slug = "fake"
            description = "fake agent"
            capabilities = []

            async def execute(self, task):
                return {}

        # Make dir(module) return FakeAgent
        mock_module_with_attr = MagicMock()
        type(mock_module_with_attr).__dir__ = lambda self: ["FakeAgent"]
        mock_module_with_attr.FakeAgent = FakeAgent
        mock_import.return_value = mock_module_with_attr

        registry.load_all()
        assert registry._loaded is True
        # Should have registered FakeAgent
        assert "fake" in registry._agents


def test_registry_load_all_import_error():
    registry = AgentRegistry()
    with patch(
        "angie.agents.registry.importlib.import_module", side_effect=ImportError("no module")
    ):
        registry.load_all()  # Should not raise
    assert registry._loaded is True


def test_registry_load_all_only_once():
    registry = AgentRegistry()
    registry._loaded = True
    with patch("angie.agents.registry.importlib.import_module") as mock_import:
        registry.load_all()
        mock_import.assert_not_called()


def test_registry_list_enabled():
    registry = AgentRegistry()
    registry.register(DummyAgent())
    registry._loaded = True
    agents = registry.list_enabled()
    assert any(a.slug == "dummy" for a in agents)


def test_agent_decorator():
    import angie.agents.registry as reg_mod

    # Save old registry
    old_registry = reg_mod._registry
    reg_mod._registry = AgentRegistry()
    reg_mod._registry._loaded = True  # Prevent load_all from running

    @agent
    class DecoratedAgent(BaseAgent):
        name = "Decorated"
        slug = "decorated"
        description = "Decorated agent"
        capabilities = []

        async def execute(self, task):
            return {}

    # Agent should be registered
    assert reg_mod._registry.get("decorated") is not None

    # Restore
    reg_mod._registry = old_registry


# ── Teams tests ───────────────────────────────────────────────────────────────


def test_team_register_and_get():
    import angie.agents.teams as teams_mod

    old_teams = teams_mod._teams.copy()
    teams_mod._teams.clear()

    try:
        team = register_team("test-team", ["dummy"])
        assert team.team_slug == "test-team"
        assert get_team("test-team") is team
    finally:
        teams_mod._teams.clear()
        teams_mod._teams.update(old_teams)


def test_team_get_nonexistent():
    assert get_team("nonexistent-xyz") is None


def test_team_all_teams():
    import angie.agents.teams as teams_mod

    old_teams = teams_mod._teams.copy()
    teams_mod._teams.clear()

    try:
        register_team("team-a", [])
        register_team("team-b", [])
        teams = all_teams()
        assert "team-a" in teams
        assert "team-b" in teams
    finally:
        teams_mod._teams.clear()
        teams_mod._teams.update(old_teams)


def test_team_resolver_agents():
    registry = AgentRegistry()
    registry.register(DummyAgent())
    registry._loaded = True

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", ["dummy", "other"])
        agents = team.agents()

    assert len(agents) == 1
    assert agents[0].slug == "dummy"


def test_team_resolver_resolve():
    registry = AgentRegistry()
    registry.register(DummyAgent())
    registry._loaded = True

    task = AngieTask(title="test dummy", user_id="u1", agent_slug="dummy")

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", ["dummy"])
        agent_obj = team.resolve(task)

    assert agent_obj is not None
    assert agent_obj.slug == "dummy"


def test_team_resolver_resolve_no_match():
    registry = AgentRegistry()
    registry.register(DummyAgent())
    registry._loaded = True

    task = AngieTask(title="something unrelated xyz", user_id="u1")

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", ["dummy"])
        result = team.resolve(task)

    assert result is None


async def test_team_resolver_execute_success():
    registry = AgentRegistry()
    registry.register(DummyAgent())
    registry._loaded = True

    task = AngieTask(title="test dummy task", user_id="u1", agent_slug="dummy")

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", ["dummy"])
        result = await team.execute(task)

    assert result["team"] == "test-team"
    assert len(result["results"]) == 1
    assert result["results"][0]["agent"] == "dummy"


async def test_team_resolver_execute_failure_continues():
    registry = AgentRegistry()
    registry.register(FailingAgent())
    registry.register(DummyAgent())
    registry._loaded = True

    task = AngieTask(title="run test dummy task", user_id="u1")

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", ["failing", "dummy"])
        result = await team.execute(task)

    # Both agents tried since failing returns status=failure
    assert result["team"] == "test-team"


async def test_team_resolver_execute_no_match():
    registry = AgentRegistry()
    registry._loaded = True

    task = AngieTask(title="zzz unrelated", user_id="u1")

    with patch("angie.agents.teams.get_registry", return_value=registry):
        team = TeamResolver("test-team", [])
        result = await team.execute(task)

    assert result["results"] == []


# ── System agent tests ────────────────────────────────────────────────────────


async def test_task_manager_list():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    result = await a.execute({"input_data": {"action": "list"}})
    assert "tasks" in result
    assert result["tasks"] == []


async def test_task_manager_cancel():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    with patch("angie.queue.celery_app.celery_app"):
        result = await a.execute({"input_data": {"action": "cancel", "task_id": "t123"}})

    assert result["cancelled"] is True
    assert result["task_id"] == "t123"


async def test_task_manager_retry():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    result = await a.execute({"input_data": {"action": "retry"}})
    assert result["retried"] is True


async def test_task_manager_unknown():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    result = await a.execute({"input_data": {"action": "unknown_action"}})
    assert "error" in result
    assert "unknown_action" in result["error"]


async def test_workflow_manager_list():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    result = await a.execute({"input_data": {"action": "list"}})
    assert "workflows" in result
    assert result["workflows"] == []


async def test_workflow_manager_trigger():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    mock_result = MagicMock()
    mock_result.id = "celery-wf-123"

    with patch("angie.queue.workers.execute_workflow") as mock_wf:
        mock_wf.delay.return_value = mock_result
        result = await a.execute({"input_data": {"action": "trigger", "workflow_id": "wf1"}})

    assert result["triggered"] is True
    assert result["workflow_id"] == "wf1"
    assert result["celery_id"] == "celery-wf-123"


async def test_workflow_manager_unknown():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    result = await a.execute({"input_data": {"action": "bad_action"}})
    assert "error" in result


async def test_event_manager_list():
    from angie.agents.system.event_manager import EventManagerAgent

    a = EventManagerAgent()
    result = await a.execute({"input_data": {"action": "list"}})
    assert "events" in result
    assert result["events"] == []


async def test_event_manager_unknown():
    from angie.agents.system.event_manager import EventManagerAgent

    a = EventManagerAgent()
    result = await a.execute({"input_data": {"action": "unknown"}})
    assert "error" in result
    assert "unknown" in result["error"]


async def test_cron_agent_create():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    mock_engine = MagicMock()

    with patch("angie.core.cron.CronEngine", return_value=mock_engine):
        result = await a.execute(
            {
                "input_data": {
                    "action": "create",
                    "expression": "0 * * * *",
                    "user_id": "user1",
                    "task_name": "my-task",
                }
            }
        )

    assert result.get("created") is True
    assert result["expression"] == "0 * * * *"


async def test_cron_agent_create_missing_expression():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    result = await a.execute({"input_data": {"action": "create", "user_id": "user1"}})
    assert "error" in result
    assert "expression" in result["error"]


async def test_cron_agent_create_missing_user_id():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    result = await a.execute({"input_data": {"action": "create", "expression": "0 * * * *"}})
    assert "error" in result
    assert "user_id" in result["error"]


async def test_cron_agent_delete():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    mock_engine = MagicMock()

    with patch("angie.core.cron.CronEngine", return_value=mock_engine):
        result = await a.execute({"input_data": {"action": "delete", "job_id": "job1"}})

    assert result.get("deleted") is True
    assert result["job_id"] == "job1"


async def test_cron_agent_delete_missing_job_id():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    result = await a.execute({"input_data": {"action": "delete"}})
    assert "error" in result
    assert "job_id" in result["error"]


async def test_cron_agent_list():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    mock_engine = MagicMock()
    mock_engine.list_crons.return_value = [{"id": "job1", "next_run": "soon"}]

    with patch("angie.core.cron.CronEngine", return_value=mock_engine):
        result = await a.execute({"input_data": {"action": "list"}})

    assert "crons" in result
    assert len(result["crons"]) == 1


async def test_cron_agent_create_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()

    with patch("angie.core.cron.CronEngine", side_effect=RuntimeError("sched error")):
        result = await a.execute(
            {
                "input_data": {
                    "action": "create",
                    "expression": "0 * * * *",
                    "user_id": "user1",
                }
            }
        )

    assert "error" in result
    assert "sched error" in result["error"]


async def test_cron_agent_delete_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()

    with patch("angie.core.cron.CronEngine", side_effect=RuntimeError("del error")):
        result = await a.execute({"input_data": {"action": "delete", "job_id": "job1"}})

    assert "error" in result


async def test_cron_agent_list_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()

    with patch("angie.core.cron.CronEngine", side_effect=RuntimeError("list error")):
        result = await a.execute({"input_data": {"action": "list"}})

    assert "error" in result
