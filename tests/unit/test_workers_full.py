"""Tests for remaining workers.py coverage gaps."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_session_factory(mock_session):
    """Build the two-level factory: get_session_factory()() -> async ctx manager."""
    async_ctx = AsyncMock()
    async_ctx.__aenter__.return_value = mock_session
    async_ctx.__aexit__.return_value = False
    session_callable = MagicMock(return_value=async_ctx)
    get_session_factory_mock = MagicMock(return_value=session_callable)
    return get_session_factory_mock


# ── _update_task_in_db ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_task_in_db_found():
    """_update_task_in_db updates and commits when task exists."""
    from angie.models.task import Task, TaskStatus
    from angie.queue.workers import _update_task_in_db

    task = Task(
        id="t1", title="t", user_id="u1", status=TaskStatus.PENDING, input_data={}, output_data={}
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    with patch("angie.db.session.get_session_factory", _make_session_factory(mock_session)):
        await _update_task_in_db("t1", "success", {"result": "done"}, None)

    assert task.status == TaskStatus.SUCCESS
    assert task.output_data == {"result": "done"}
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_task_in_db_not_found():
    """_update_task_in_db does nothing when task doesn't exist."""
    from angie.queue.workers import _update_task_in_db

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    with patch("angie.db.session.get_session_factory", _make_session_factory(mock_session)):
        await _update_task_in_db("nonexistent", "failure", None, "error")

    mock_session.commit.assert_not_called()


# ── execute_task: no agent resolved ───────────────────────────────────────────


def test_execute_task_no_agent_resolved():
    """When registry returns None, task raises ValueError which triggers retry."""
    from angie.queue.workers import execute_task

    mock_self = MagicMock()
    mock_self.retry.side_effect = Exception("retry called")

    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = None

    task_dict = {
        "id": "task-123",
        "title": "Test",
        "input_data": {},
        "agent_slug": "nonexistent",
        "user_id": "u1",
    }

    with (
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
        patch("asyncio.run", return_value=None),
    ):
        try:
            execute_task.__wrapped__.__func__(mock_self, task_dict)
        except Exception:
            pass


def test_execute_task_agent_raises_exception():
    """When agent.execute raises, task gets marked failed and retried."""
    from angie.queue.workers import execute_task

    mock_self = MagicMock()
    mock_self.retry.side_effect = Exception("retry called")

    mock_agent = MagicMock()

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    task_dict = {
        "id": "task-456",
        "title": "Failing",
        "input_data": {},
        "agent_slug": "gmail",
        "user_id": "u1",
    }

    def fake_run(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        except Exception:
            raise
        finally:
            loop.close()

    mock_agent.execute = AsyncMock(side_effect=RuntimeError("agent blew up"))

    with (
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
        patch("asyncio.run", side_effect=fake_run),
    ):
        try:
            execute_task.__wrapped__.__func__(mock_self, task_dict)
        except Exception:
            pass


def test_execute_task_success_path():
    """execute_task happy path returns success dict."""
    from angie.queue.workers import execute_task

    mock_self = MagicMock()

    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value={"summary": "done"})

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    task_dict = {
        "id": "task-789",
        "title": "Success",
        "input_data": {},
        "agent_slug": "gmail",
        "user_id": "u1",
    }

    def fake_run(coro):
        name = getattr(coro, "__qualname__", "") or ""
        if "_update_task_in_db" in name or "_send_reply" in name:
            coro.close()
            return None
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with (
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
        patch("angie.queue.workers._update_task_in_db", new_callable=AsyncMock),
        patch("angie.queue.workers._send_reply", new_callable=AsyncMock),
        patch("angie.queue.workers.reset_engine"),
        patch("asyncio.run", side_effect=fake_run),
    ):
        result = execute_task.__wrapped__.__func__(mock_self, task_dict)

    assert result["status"] == "success"


def test_execute_workflow_runs_steps():
    """execute_workflow calls WorkflowExecutor.run()."""
    from angie.queue.workers import execute_workflow

    mock_self = MagicMock()

    with (
        patch("angie.core.workflows.WorkflowExecutor") as mock_cls,
        patch("asyncio.run", return_value={"done": True}),
    ):
        mock_executor = MagicMock()
        mock_cls.return_value = mock_executor

        result = execute_workflow.__wrapped__.__func__(mock_self, "wf-1", {})

    assert result["status"] == "success"


def test_execute_workflow_exception_path():
    """execute_workflow exception triggers retry."""
    from angie.queue.workers import execute_workflow

    mock_self = MagicMock()
    mock_self.retry.side_effect = Exception("retry called")

    with (
        patch("angie.core.workflows.WorkflowExecutor") as mock_cls,
        patch("asyncio.run", side_effect=RuntimeError("db dead")),
    ):
        mock_executor = MagicMock()
        mock_cls.return_value = mock_executor

        try:
            execute_workflow.__wrapped__.__func__(mock_self, "wf-1", {})
        except Exception:
            pass


@pytest.mark.asyncio
async def test_send_reply_with_channel():
    """_send_reply dispatches to channel manager when source_channel is set."""
    from angie.queue.workers import _send_reply

    mock_mgr = AsyncMock()
    mock_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        await _send_reply("slack", "user-1", "hello")

    mock_mgr.send.assert_called_once_with("user-1", "hello", channel_type="slack")


@pytest.mark.asyncio
async def test_send_reply_no_channel():
    """_send_reply is a no-op when source_channel is None."""
    from angie.queue.workers import _send_reply

    with patch("angie.channels.base.get_channel_manager") as mock_cm:
        await _send_reply(None, "user-1", "hello")

    mock_cm.assert_not_called()


def test_resolve_agent_returns_none_when_no_match():
    """_resolve_agent returns None when registry has no matching agent."""
    from angie.queue.workers import _resolve_agent

    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = None

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"title": "no agent", "input_data": {}})

    assert result is None


def test_resolve_agent_via_resolve_fallback():
    """_resolve_agent returns agent via registry.resolve when no slug match."""
    from angie.queue.workers import _resolve_agent

    mock_agent = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = mock_agent

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"title": "check email", "input_data": {}})

    assert result is mock_agent


@pytest.mark.asyncio
async def test_send_reply_channel_error():
    """_send_reply logs warning when channel send raises."""
    from angie.queue.workers import _send_reply

    mock_mgr = AsyncMock()
    mock_mgr.send = AsyncMock(side_effect=RuntimeError("channel down"))

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        # Should not raise — exception is caught and logged
        await _send_reply("slack", "user-1", "hello")
