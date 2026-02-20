"""Tests for angie.core.workflows (WorkflowExecutor)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


def _make_session_factory(session):
    @asynccontextmanager
    async def _factory():
        yield session

    class _SF:
        def __call__(self):
            return _factory()

    return _SF()


async def test_run_workflow_not_found():
    from angie.core.workflows import WorkflowExecutor

    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)):
        executor = WorkflowExecutor()
        result = await executor.run("missing-wf", {})

    assert result["status"] == "failed"
    assert "not found" in result["error"]


async def test_run_workflow_disabled():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = False

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf

    with patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", {})

    assert result["status"] == "skipped"
    assert "disabled" in result["error"]


async def test_run_workflow_no_steps_success():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    with patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", {})

    assert result["status"] == "success"
    assert result["results"] == []


async def test_run_workflow_with_dict_steps():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    mock_agent = AsyncMock()
    mock_agent.slug = "test-agent"
    mock_agent.execute.return_value = {"status": "ok", "output": "done"}

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    steps = [{"agent_slug": "test-agent", "on_failure": "stop"}]
    context = {"steps": steps}

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", context)

    assert result["status"] == "success"
    assert len(result["results"]) == 1
    assert result["results"][0]["agent"] == "test-agent"


async def test_run_workflow_agent_not_found_stop():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    mock_registry = MagicMock()
    mock_registry.get.return_value = None

    steps = [{"agent_slug": "missing", "on_failure": "stop"}]
    context = {"steps": steps}

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", context)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


async def test_run_workflow_agent_not_found_continue():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    mock_registry = MagicMock()
    mock_registry.get.return_value = None

    steps = [{"agent_slug": "missing", "on_failure": "continue"}]
    context = {"steps": steps}

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", context)

    assert result["status"] == "success"


async def test_run_workflow_step_exception_stop():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    mock_agent = AsyncMock()
    mock_agent.slug = "bad-agent"
    mock_agent.execute.side_effect = RuntimeError("boom")

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    steps = [{"agent_slug": "bad-agent", "on_failure": "stop"}]
    context = {"steps": steps}

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", context)

    assert result["status"] == "failed"
    assert "boom" in result["error"]


async def test_run_workflow_step_exception_continue():
    from angie.core.workflows import WorkflowExecutor

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_steps_result

    mock_agent = AsyncMock()
    mock_agent.slug = "bad-agent"
    mock_agent.execute.side_effect = RuntimeError("boom")

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    steps = [{"agent_slug": "bad-agent", "on_failure": "continue"}]
    context = {"steps": steps}

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", context)

    assert result["status"] == "success"


async def test_run_workflow_with_model_steps():
    """Test using WorkflowStep model objects (not dicts)."""
    from angie.core.workflows import WorkflowExecutor
    from angie.models.workflow import WorkflowStep

    mock_wf = MagicMock()
    mock_wf.is_enabled = True

    mock_step = MagicMock(spec=WorkflowStep)
    mock_step.config = {"agent_slug": "test-agent"}
    mock_step.on_failure = "stop"
    mock_step.name = "Step 1"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_wf
    mock_steps_result = MagicMock()
    mock_steps_result.scalars.return_value.all.return_value = [mock_step]
    mock_session.execute.return_value = mock_steps_result

    mock_agent = AsyncMock()
    mock_agent.slug = "test-agent"
    mock_agent.execute.return_value = {"status": "ok"}

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    with (
        patch("angie.db.session.get_session_factory", return_value=_make_session_factory(mock_session)),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        executor = WorkflowExecutor()
        result = await executor.run("wf1", {})

    assert result["status"] == "success"
    assert len(result["results"]) == 1
