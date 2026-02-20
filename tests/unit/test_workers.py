"""Tests for angie.queue.workers."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_resolve_agent_by_slug():
    from angie.queue.workers import _resolve_agent

    mock_agent = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"agent_slug": "test-agent", "title": "do stuff"})

    assert result is mock_agent
    mock_registry.get.assert_called_once_with("test-agent")


def test_resolve_agent_slug_not_found_falls_back():
    from angie.queue.workers import _resolve_agent

    mock_agent = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = mock_agent

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"agent_slug": "test-agent", "title": "do stuff"})

    assert result is mock_agent


def test_resolve_agent_no_match():
    from angie.queue.workers import _resolve_agent

    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = None

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"title": "nothing matches"})

    assert result is None


def test_resolve_agent_no_slug_uses_resolve():
    from angie.queue.workers import _resolve_agent

    mock_agent = MagicMock()
    mock_registry = MagicMock()
    mock_registry.resolve.return_value = mock_agent

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = _resolve_agent({"title": "do something"})

    assert result is mock_agent
    mock_registry.get.assert_not_called()


async def test_send_reply_no_channel():
    from angie.queue.workers import _send_reply

    with patch("angie.channels.base.get_channel_manager") as mock_mgr_fn:
        await _send_reply(None, "user1", "hello")
        mock_mgr_fn.assert_not_called()


async def test_send_reply_no_user():
    from angie.queue.workers import _send_reply

    with patch("angie.channels.base.get_channel_manager") as mock_mgr_fn:
        await _send_reply("slack", None, "hello")
        mock_mgr_fn.assert_not_called()


async def test_send_reply_success():
    from angie.queue.workers import _send_reply

    mock_mgr = MagicMock()
    mock_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        await _send_reply("slack", "user1", "hello")

    mock_mgr.send.assert_called_once_with("user1", "hello", channel_type="slack")


async def test_send_reply_channel_error():
    from angie.queue.workers import _send_reply

    mock_mgr = MagicMock()
    mock_mgr.send = AsyncMock(side_effect=Exception("channel down"))

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        # Should not raise
        await _send_reply("slack", "user1", "hello")


def test_execute_task_success():
    from angie.queue.workers import execute_task

    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value={"summary": "Done!", "status": "ok"})

    task_dict = {
        "id": "task-1",
        "title": "Test task",
        "user_id": "user1",
        "source_channel": "slack",
        "input_data": {},
    }

    with (
        patch("angie.queue.workers._resolve_agent", return_value=mock_agent),
        patch("angie.queue.workers.asyncio.run") as mock_run,
        patch("angie.queue.workers._update_task_in_db"),
        patch("angie.queue.workers._send_reply"),
    ):
        mock_run.side_effect = lambda coro: _run_sync(coro)
        result = execute_task(task_dict)

    assert result["status"] == "success"
    assert result["task_id"] == "task-1"


def test_execute_task_no_agent():
    from angie.queue.workers import execute_task

    task_dict = {
        "id": "task-1",
        "title": "Nothing",
        "user_id": "user1",
        "source_channel": None,
        "input_data": {},
    }

    # Create a mock self for the task
    mock_self = MagicMock()
    mock_self.request.retries = 0
    mock_self.retry = MagicMock(side_effect=Exception("retry"))

    with (
        patch("angie.queue.workers._resolve_agent", return_value=None),
        patch("angie.queue.workers.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None

        try:
            execute_task.__wrapped__(mock_self, task_dict)
        except Exception:
            pass  # Expected retry exception


def test_execute_workflow():
    from angie.queue.workers import execute_workflow

    with (
        patch("angie.core.workflows.WorkflowExecutor"),
        patch("angie.queue.workers.asyncio.run") as mock_run,
    ):
        mock_run.return_value = {"status": "success", "results": []}
        result = execute_workflow.apply(args=["wf1", {"steps": []}])

    assert result.result["workflow_id"] == "wf1"


def test_execute_workflow_failure():
    from angie.queue.workers import execute_workflow

    with (
        patch("angie.core.workflows.WorkflowExecutor", side_effect=RuntimeError("executor down")),
        patch("angie.queue.workers.asyncio.run"),
    ):
        result = execute_workflow.apply(args=["wf1", {}])

    # Task should fail
    assert result.failed()


def _run_sync(coro):
    """Synchronously run a coroutine using a new event loop."""
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()
