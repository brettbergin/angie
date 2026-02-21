"""Tests for angie.core.tasks (AngieTask, TaskDispatcher)."""

from unittest.mock import MagicMock, patch

from angie.core.tasks import AngieTask, TaskDispatcher, get_dispatcher


def test_angie_task_to_dict():
    task = AngieTask(
        title="Test task",
        user_id="user1",
        input_data={"key": "val"},
        agent_slug="my-agent",
        workflow_id="wf-1",
        source_event_id="ev-1",
        source_channel="slack",
    )
    d = task.to_dict()
    assert d["title"] == "Test task"
    assert d["user_id"] == "user1"
    assert d["input_data"] == {"key": "val"}
    assert d["agent_slug"] == "my-agent"
    assert d["workflow_id"] == "wf-1"
    assert d["source_event_id"] == "ev-1"
    assert d["source_channel"] == "slack"
    assert "id" in d
    assert "created_at" in d


def test_angie_task_defaults():
    task = AngieTask(title="Simple task", user_id="u1")
    assert task.input_data == {}
    assert task.agent_slug is None
    assert task.workflow_id is None
    assert task.source_event_id is None
    assert task.source_channel is None
    assert task.id is not None


def test_task_dispatcher_dispatch():
    dispatcher = TaskDispatcher()
    mock_result = MagicMock()
    mock_result.id = "celery-id-123"

    with patch("angie.queue.celery_app.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        task = AngieTask(title="Test", user_id="u1")
        celery_id = dispatcher.dispatch(task)

    assert celery_id == "celery-id-123"
    mock_celery.send_task.assert_called_once()


def test_task_dispatcher_dispatch_from_event():
    from angie.core.events import AngieEvent
    from angie.models.event import EventType

    dispatcher = TaskDispatcher()
    mock_result = MagicMock()
    mock_result.id = "celery-event-id"

    event = AngieEvent(
        type=EventType.USER_MESSAGE,
        payload={"text": "hello"},
        user_id="user1",
        source_channel="discord",
    )

    with patch("angie.queue.celery_app.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        task = dispatcher.dispatch_from_event(event, agent_slug="test-agent")

    assert task.id == "celery-event-id"
    assert task.user_id == "user1"
    assert task.agent_slug == "test-agent"
    assert task.source_channel == "discord"
    assert task.source_event_id == event.id


def test_task_dispatcher_dispatch_from_event_no_user():
    from angie.core.events import AngieEvent
    from angie.models.event import EventType

    dispatcher = TaskDispatcher()
    mock_result = MagicMock()
    mock_result.id = "celery-sys"

    event = AngieEvent(type=EventType.SYSTEM, payload={})

    with patch("angie.queue.celery_app.celery_app") as mock_celery:
        mock_celery.send_task.return_value = mock_result
        task = dispatcher.dispatch_from_event(event)

    assert task.user_id == "system"
    assert task.agent_slug is None


def test_get_dispatcher_singleton():
    import angie.core.tasks as tasks_mod

    tasks_mod._dispatcher = None
    d1 = get_dispatcher()
    d2 = get_dispatcher()
    assert d1 is d2
    tasks_mod._dispatcher = None
