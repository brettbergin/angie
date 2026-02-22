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
    mock_pm.compose_for_agent.assert_called_once_with("dummy", agent_instructions="")


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


def test_task_manager_list_tool():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["list_tasks"]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock(return_value=mock_session)
    with patch("angie.db.session.get_session_factory", return_value=mock_factory):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(tool.function())
    assert "tasks" in result
    assert result["tasks"] == []


def test_task_manager_cancel_tool():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["cancel_task"]
    with patch("angie.queue.celery_app.celery_app"):
        result = tool.function(task_id="t123")
    assert result["cancelled"] is True
    assert result["task_id"] == "t123"


def test_task_manager_retry_tool():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["retry_task"]

    mock_task = MagicMock()
    mock_task.id = "task42"
    mock_task.status = MagicMock()
    mock_task.status.__eq__ = MagicMock(return_value=False)

    from angie.models.task import TaskStatus

    mock_task.status = TaskStatus.FAILURE
    mock_task.retry_count = 0
    mock_task.error = "some error"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock(return_value=mock_session)
    mock_celery_result = MagicMock()
    mock_celery_result.id = "celery-retry-123"
    with (
        patch("angie.db.session.get_session_factory", return_value=mock_factory),
        patch("angie.queue.workers.execute_task") as mock_exec,
    ):
        mock_exec.delay.return_value = mock_celery_result
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(tool.function(task_id="task42"))
    assert result["retried"] is True


async def test_task_manager_execute():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    mock_result = MagicMock(output="Listing tasks...")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"title": "list tasks"})
    assert result == {"result": "Listing tasks..."}


async def test_task_manager_execute_error():
    from angie.agents.system.task_manager import TaskManagerAgent

    a = TaskManagerAgent()
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(side_effect=RuntimeError("LLM error"))
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"input_data": {"action": "unknown_action"}})
    assert "error" in result


def test_workflow_manager_list_tool():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["list_workflows"]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock(return_value=mock_session)
    with patch("angie.db.session.get_session_factory", return_value=mock_factory):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(tool.function())
    assert "workflows" in result
    assert result["workflows"] == []


def test_workflow_manager_trigger_tool():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["trigger_workflow"]
    mock_result = MagicMock()
    mock_result.id = "celery-wf-123"
    with patch("angie.queue.workers.execute_workflow") as mock_wf:
        mock_wf.delay.return_value = mock_result
        result = tool.function(workflow_id="wf1")
    assert result["triggered"] is True
    assert result["workflow_id"] == "wf1"
    assert result["celery_id"] == "celery-wf-123"


async def test_workflow_manager_execute():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    mock_result = MagicMock(output="Triggered workflow")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"title": "trigger wf1"})
    assert result == {"result": "Triggered workflow"}


async def test_workflow_manager_execute_error():
    from angie.agents.system.workflow_manager import WorkflowManagerAgent

    a = WorkflowManagerAgent()
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(side_effect=RuntimeError("err"))
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"input_data": {"action": "bad_action"}})
    assert "error" in result


def test_event_manager_list_tool():
    from angie.agents.system.event_manager import EventManagerAgent

    a = EventManagerAgent()
    tool = a.build_pydantic_agent()._function_toolset.tools["list_events"]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock(return_value=mock_session)
    with patch("angie.db.session.get_session_factory", return_value=mock_factory):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(tool.function())
    assert "events" in result
    assert result["events"] == []


async def test_event_manager_execute():
    from angie.agents.system.event_manager import EventManagerAgent

    a = EventManagerAgent()
    mock_result = MagicMock(output="Events: ...")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"title": "list events"})
    assert result == {"result": "Events: ..."}


async def test_event_manager_execute_error():
    from angie.agents.system.event_manager import EventManagerAgent

    a = EventManagerAgent()
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(side_effect=RuntimeError("err"))
    with (
        patch.object(a, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"input_data": {"action": "unknown"}})
    assert "error" in result


async def test_cron_agent_create_tool():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["create_scheduled_task"]
    mock_create = AsyncMock(
        return_value={
            "created": True,
            "job_id": "j1",
            "name": "t",
            "expression": "0 * * * *",
            "human_readable": "Every hour",
        }
    )
    with patch("angie.agents.system.cron._create_job_in_db", mock_create):
        result = await tool.function(
            expression="0 * * * *",
            task_name="my-task",
        )
    assert result["created"] is True
    assert result["expression"] == "0 * * * *"


async def test_cron_agent_create_missing_expression():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["create_scheduled_task"]
    result = await tool.function(expression="", task_name="my-task")
    assert "error" in result
    assert "expression" in result["error"]


async def test_cron_agent_create_missing_user_id():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    # Build without user_id to test the guard
    tool = a.build_pydantic_agent(user_id="")._function_toolset.tools["create_scheduled_task"]
    result = await tool.function(expression="0 * * * *", task_name="my-task")
    assert "error" in result
    assert "user_id" in result["error"]


async def test_cron_agent_create_missing_task_name():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["create_scheduled_task"]
    result = await tool.function(expression="0 * * * *", task_name="")
    assert "error" in result
    assert "task_name" in result["error"]


async def test_cron_agent_delete_tool():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["delete_scheduled_task"]
    mock_delete = AsyncMock(return_value={"deleted": True, "job_id": "job1"})
    with patch("angie.agents.system.cron._delete_job_from_db", mock_delete):
        result = await tool.function(job_id="job1")
    assert result["deleted"] is True
    assert result["job_id"] == "job1"


async def test_cron_agent_delete_missing_job_id():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["delete_scheduled_task"]
    result = await tool.function(job_id="")
    assert "error" in result
    assert "job_id" in result["error"]


async def test_cron_agent_list_tool():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["list_scheduled_tasks"]
    mock_list = AsyncMock(return_value={"schedules": [{"id": "job1", "name": "test"}]})
    with patch("angie.agents.system.cron._list_jobs_from_db", mock_list):
        result = await tool.function()
    assert "schedules" in result
    assert len(result["schedules"]) == 1


async def test_cron_agent_create_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["create_scheduled_task"]
    with patch(
        "angie.agents.system.cron._create_job_in_db",
        AsyncMock(side_effect=RuntimeError("sched error")),
    ):
        result = await tool.function(expression="0 * * * *", task_name="t")
    assert "error" in result
    assert "sched error" in result["error"]


async def test_cron_agent_delete_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["delete_scheduled_task"]
    with patch(
        "angie.agents.system.cron._delete_job_from_db",
        AsyncMock(side_effect=RuntimeError("del error")),
    ):
        result = await tool.function(job_id="job1")
    assert "error" in result


async def test_cron_agent_list_exception():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    tool = a.build_pydantic_agent(user_id="user1")._function_toolset.tools["list_scheduled_tasks"]
    with patch(
        "angie.agents.system.cron._list_jobs_from_db",
        AsyncMock(side_effect=RuntimeError("list error")),
    ):
        result = await tool.function()
    assert "error" in result


async def test_cron_agent_execute():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    mock_result = MagicMock(output="Created cron job...")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(a, "build_pydantic_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"title": "create cron at midnight", "user_id": "u1"})
    assert result == {"result": "Created cron job..."}


async def test_cron_agent_execute_error():
    from angie.agents.system.cron import CronAgent

    a = CronAgent()
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(side_effect=RuntimeError("fail"))
    with (
        patch.object(a, "build_pydantic_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await a.execute({"input_data": {"action": "create"}, "user_id": "u1"})
    assert "error" in result
