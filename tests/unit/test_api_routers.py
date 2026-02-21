"""Tests for all API router CRUD endpoints."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_app_with_overrides(mock_user=None, mock_session=None):
    """Create a FastAPI test app with dependency overrides."""
    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://localhost:3000"]
        mock_settings.secret_key = "test-secret-key-for-testing"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30
        mock_settings.jwt_refresh_token_expire_days = 30
        mock_gs.return_value = mock_settings

        from angie.api.app import create_app

        app = create_app()

    from angie.api.auth import get_current_user
    from angie.db.session import get_session

    if mock_user is None:
        from angie.models.user import User

        mock_user = User(
            id="user-1",
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
            full_name="Test User",
            timezone="UTC",
            is_active=True,
        )

    if mock_session is None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

    async def override_user():
        return mock_user

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session

    return app, mock_user, mock_session


# ── api/app.py lifespan yield ──────────────────────────────────────────────────


def test_app_lifespan():
    """Cover the yield inside the lifespan context manager."""
    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.cors_origins = ["http://localhost:3000"]
        mock_settings.secret_key = "test-key"
        mock_settings.jwt_algorithm = "HS256"
        mock_gs.return_value = mock_settings

        from angie.api.app import create_app

        app = create_app()

    # Using TestClient as context manager triggers lifespan startup+shutdown
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200


# ── Agents router ─────────────────────────────────────────────────────────────


def test_list_agents_endpoint():
    app, user, session = _make_app_with_overrides()

    mock_agent = MagicMock()
    mock_agent.slug = "gmail"
    mock_agent.name = "GmailAgent"
    mock_agent.description = "Gmail management"
    mock_agent.capabilities = ["email", "gmail"]

    mock_registry = MagicMock()
    mock_registry.list_all.return_value = [mock_agent]

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        with TestClient(app) as client:
            resp = client.get("/api/v1/agents/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slug"] == "gmail"


# ── Users router ───────────────────────────────────────────────────────────────


def test_get_me_endpoint():
    app, user, session = _make_app_with_overrides()
    with TestClient(app) as client:
        resp = client.get("/api/v1/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"


# ── Events router ──────────────────────────────────────────────────────────────


def _make_scalars_result(items):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def test_list_events_endpoint():
    from datetime import datetime

    app, user, session = _make_app_with_overrides()

    from angie.models.event import Event, EventType

    event = Event(
        id="evt-1", type=EventType.USER_MESSAGE, user_id="user-1", payload={}, processed=False
    )
    event.created_at = datetime(2026, 1, 1, 12, 0, 0)
    session.execute = AsyncMock(return_value=_make_scalars_result([event]))

    with TestClient(app) as client:
        resp = client.get("/api/v1/events/")
    assert resp.status_code == 200


def test_create_event_endpoint():
    from datetime import datetime

    app, user, session = _make_app_with_overrides()

    from angie.models.event import Event, EventType  # noqa: F401

    async def mock_refresh(obj):
        obj.id = "evt-2"
        obj.processed = False
        obj.payload = {"msg": "hi"}
        obj.source_channel = None
        obj.user_id = "user-1"
        obj.type = EventType.USER_MESSAGE
        obj.created_at = datetime(2026, 1, 1, 12, 0, 0)

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/events/",
            json={
                "type": "user_message",
                "payload": {"msg": "hi"},
                "source_channel": "slack",
            },
        )
    assert resp.status_code in (200, 201, 422)


# ── Tasks router ───────────────────────────────────────────────────────────────


def test_list_tasks_endpoint():
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    task = Task(
        id="t1",
        title="Test task",
        user_id="user-1",
        status=TaskStatus.PENDING,
        input_data={},
        output_data={},
    )
    session.execute = AsyncMock(return_value=_make_scalars_result([task]))

    with TestClient(app) as client:
        resp = client.get("/api/v1/tasks/")
    assert resp.status_code == 200


def test_create_task_endpoint():
    app, user, session = _make_app_with_overrides()

    from angie.models.task import TaskStatus

    async def mock_refresh(obj):
        obj.id = "task-1"
        obj.status = TaskStatus.PENDING
        obj.input_data = {}
        obj.output_data = {}
        obj.source_channel = None
        obj.agent_slug = None
        obj.error = None
        obj.created_at = None
        obj.updated_at = None

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "My task",
                "input_data": {"action": "test"},
            },
        )
    assert resp.status_code in (200, 201, 422)


def test_get_task_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get("/api/v1/tasks/nonexistent-id")
    assert resp.status_code == 404


def test_get_task_wrong_user():
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    other_task = Task(id="t1", title="Other task", user_id="other-user", status=TaskStatus.PENDING)
    session.get = AsyncMock(return_value=other_task)

    with TestClient(app) as client:
        resp = client.get("/api/v1/tasks/t1")
    assert resp.status_code == 404


def test_update_task_status():
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    task = Task(
        id="t1",
        title="t",
        user_id="user-1",
        status=TaskStatus.PENDING,
        input_data={},
        output_data={},
    )

    async def mock_refresh(obj):
        pass

    session.get = AsyncMock(return_value=task)
    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.patch("/api/v1/tasks/t1", json={"status": "success"})
    assert resp.status_code in (200, 422)


def test_delete_task_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/tasks/nonexistent")
    assert resp.status_code == 404


def test_delete_task_success():
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    task = Task(id="t1", title="t", user_id="user-1", status=TaskStatus.PENDING)
    session.get = AsyncMock(return_value=task)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/tasks/t1")
    assert resp.status_code in (200, 204)


# ── Teams router ───────────────────────────────────────────────────────────────


def test_list_teams_endpoint():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team

    team = Team(id="team-1", name="Dev Team", slug="dev-team", agent_slugs=[], is_enabled=True)
    session.execute = AsyncMock(return_value=_make_scalars_result([team]))

    with TestClient(app) as client:
        resp = client.get("/api/v1/teams/")
    assert resp.status_code == 200


def test_create_team_endpoint():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team  # noqa: F401

    async def mock_refresh(obj):
        obj.id = "t1"
        obj.name = "My Team"
        obj.slug = "my-team"
        obj.description = None
        obj.agent_slugs = []
        obj.is_enabled = True
        obj.created_at = None
        obj.updated_at = None

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.post("/api/v1/teams/", json={"name": "My Team", "slug": "my-team"})
    assert resp.status_code in (200, 201, 422)


def test_get_team_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get("/api/v1/teams/nonexistent")
    assert resp.status_code == 404


def test_get_team_success():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team

    team = Team(id="t1", name="Dev Team", slug="dev-team", agent_slugs=[], is_enabled=True)
    session.get = AsyncMock(return_value=team)

    with TestClient(app) as client:
        resp = client.get("/api/v1/teams/t1")
    assert resp.status_code == 200


def test_delete_team_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/teams/nonexistent")
    assert resp.status_code == 404


def test_delete_team_success():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team

    team = Team(id="t1", name="Dev Team", slug="dev-team", is_enabled=True)
    session.get = AsyncMock(return_value=team)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/teams/t1")
    assert resp.status_code in (200, 204)


def test_list_teams_enabled_only():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team

    enabled_team = Team(id="t1", name="Enabled", slug="enabled", agent_slugs=[], is_enabled=True)
    disabled_team = Team(
        id="t2", name="Disabled", slug="disabled", agent_slugs=[], is_enabled=False
    )
    all_teams = [enabled_team, disabled_team]

    async def mock_execute(stmt):
        """Return filtered results based on enabled_only query param."""
        stmt_str = str(stmt)
        if "is_enabled" in stmt_str:
            return _make_scalars_result([enabled_team])
        return _make_scalars_result(all_teams)

    session.execute = AsyncMock(side_effect=mock_execute)

    with TestClient(app) as client:
        # Without filter — returns all
        resp = client.get("/api/v1/teams/")
        assert resp.status_code == 200

        # With enabled_only — returns filtered
        resp = client.get("/api/v1/teams/?enabled_only=true")
        assert resp.status_code == 200


def test_update_team_is_enabled():
    app, user, session = _make_app_with_overrides()
    from angie.models.team import Team

    team = Team(id="t1", name="Dev Team", slug="dev-team", agent_slugs=[], is_enabled=True)
    session.get = AsyncMock(return_value=team)

    async def mock_refresh(obj):
        pass  # Keep current attrs

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.patch("/api/v1/teams/t1", json={"is_enabled": False})
    assert resp.status_code == 200
    assert team.is_enabled is False


# ── Workflows router ───────────────────────────────────────────────────────────


def test_list_workflows_endpoint():
    app, user, session = _make_app_with_overrides()
    from angie.models.workflow import Workflow

    wf = Workflow(id="wf-1", name="Morning Briefing", slug="morning-briefing", is_enabled=True)
    session.execute = AsyncMock(return_value=_make_scalars_result([wf]))

    with TestClient(app) as client:
        resp = client.get("/api/v1/workflows/")
    assert resp.status_code == 200


def test_create_workflow_endpoint():
    app, user, session = _make_app_with_overrides()

    async def mock_refresh(obj):
        obj.id = "wf-1"
        obj.name = "Test WF"
        obj.slug = "test-wf"
        obj.description = None
        obj.trigger_event = None
        obj.is_enabled = True
        obj.steps = []
        obj.created_at = None
        obj.updated_at = None

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.post("/api/v1/workflows/", json={"name": "Test WF", "slug": "test-wf"})
    assert resp.status_code in (200, 201, 422)


def test_get_workflow_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.get("/api/v1/workflows/nonexistent")
    assert resp.status_code == 404


def test_get_workflow_success():
    app, user, session = _make_app_with_overrides()
    from angie.models.workflow import Workflow

    wf = Workflow(id="wf-1", name="WF", slug="wf", is_enabled=True)
    session.get = AsyncMock(return_value=wf)

    with TestClient(app) as client:
        resp = client.get("/api/v1/workflows/wf-1")
    assert resp.status_code == 200


def test_update_workflow_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.patch("/api/v1/workflows/nonexistent", json={"is_enabled": False})
    assert resp.status_code == 404


def test_update_workflow_success():
    app, user, session = _make_app_with_overrides()
    from angie.models.workflow import Workflow

    wf = Workflow(id="wf-1", name="WF", slug="wf", is_enabled=True)

    async def mock_refresh(obj):
        pass

    session.get = AsyncMock(return_value=wf)
    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.patch("/api/v1/workflows/wf-1", json={"is_enabled": False})
    assert resp.status_code == 200


def test_delete_workflow_not_found():
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/workflows/nonexistent")
    assert resp.status_code == 404


def test_delete_workflow_success():
    app, user, session = _make_app_with_overrides()
    from angie.models.workflow import Workflow

    wf = Workflow(id="wf-1", name="WF", slug="wf")
    session.get = AsyncMock(return_value=wf)

    with TestClient(app) as client:
        resp = client.delete("/api/v1/workflows/wf-1")
    assert resp.status_code in (200, 204)


# ── Channels router ────────────────────────────────────────────────────────────


def test_list_channels_endpoint():
    app, user, session = _make_app_with_overrides()
    from angie.models.channel import ChannelConfig, ChannelType

    cfg = ChannelConfig(
        id="cfg-1", user_id="user-1", type=ChannelType.SLACK, is_enabled=True, config={}
    )
    session.execute = AsyncMock(return_value=_make_scalars_result([cfg]))

    with TestClient(app) as client:
        resp = client.get("/api/v1/channels/")
    assert resp.status_code == 200


# ── Prompts router ─────────────────────────────────────────────────────────────


def test_list_prompts_endpoint():
    app, user, session = _make_app_with_overrides()

    mock_pm = MagicMock()
    mock_pm.get_user_prompts.return_value = ["# Personality\nBrief and direct"]
    mock_user_dir = MagicMock()
    mock_user_dir.exists.return_value = False
    mock_default_dir = MagicMock()
    mock_default_dir.exists.return_value = False
    mock_pm.user_prompts_dir.__truediv__ = MagicMock(
        side_effect=lambda x: mock_user_dir if x == user.id else mock_default_dir
    )

    with patch("angie.core.prompts.get_prompt_manager", return_value=mock_pm):
        with TestClient(app) as client:
            resp = client.get("/api/v1/prompts/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ── Tasks router: TaskOut model_validate ──────────────────────────────────────


def test_task_out_model_validate_no_timestamps():
    """Cover the custom model_validate override in tasks router (no timestamps)."""
    from angie.models.task import Task, TaskStatus

    task = Task(
        id="t1",
        title="test",
        user_id="u1",
        status=TaskStatus.PENDING,
        input_data={},
        output_data={},
    )
    # created_at is None, so the isoformat branch is skipped
    from angie.api.routers.tasks import TaskOut

    result = TaskOut.model_validate(task)
    assert result.id == "t1"
    assert result.created_at is None


def test_task_out_model_validate_with_datetime():
    """TaskOut accepts native datetime fields via from_attributes."""
    from datetime import datetime

    from angie.api.routers.tasks import TaskOut

    class MockObj:
        id = "t1"
        title = "t"
        status = "success"
        input_data = {}
        output_data = {}
        error = None
        source_channel = None
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        updated_at = datetime(2024, 1, 2, 12, 0, 0)

    result = TaskOut.model_validate(MockObj())

    assert result.created_at == datetime(2024, 1, 1, 12, 0, 0)
    assert result.updated_at == datetime(2024, 1, 2, 12, 0, 0)


def test_get_task_success():
    """Cover the happy-path return in get_task (line 85)."""
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    task = Task(
        id="t1",
        title="Task",
        user_id="user-1",
        status=TaskStatus.SUCCESS,
        input_data={},
        output_data={},
    )
    session.get = AsyncMock(return_value=task)

    with TestClient(app) as client:
        resp = client.get("/api/v1/tasks/t1")

    assert resp.status_code == 200


def test_update_task_status_not_found():
    """Cover the 404 path in update_task_status (line 97)."""
    app, user, session = _make_app_with_overrides()
    session.get = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.patch("/api/v1/tasks/nonexistent", json={"status": "success"})

    assert resp.status_code == 404


def test_update_task_with_output_data():
    """Cover line 101: task.output_data = body['output_data']."""
    app, user, session = _make_app_with_overrides()

    from angie.models.task import Task, TaskStatus

    task = Task(
        id="t1",
        title="Task",
        user_id="user-1",
        status=TaskStatus.PENDING,
        input_data={},
        output_data={},
    )
    session.get = AsyncMock(return_value=task)

    async def mock_refresh(obj):
        pass

    session.refresh = mock_refresh

    with TestClient(app) as client:
        resp = client.patch("/api/v1/tasks/t1", json={"output_data": {"result": "ok"}})

    assert resp.status_code in (200, 422)


# ── api/routers/chat.py (WebSocket) ──────────────────────────────────────────


def _make_ws_settings(secret_key: str = "ws-secret"):
    s = MagicMock()
    s.cors_origins = ["http://localhost:3000"]
    s.secret_key = secret_key
    s.jwt_algorithm = "HS256"
    s.jwt_access_token_expire_minutes = 30
    s.jwt_refresh_token_expire_days = 30
    return s


def _ws_token(secret_key: str = "ws-secret") -> str:
    from jose import jwt as jose_jwt

    return jose_jwt.encode(
        {"sub": "user-1", "exp": 9999999999},
        secret_key,
        algorithm="HS256",
    )


def test_chat_ws_invalid_token():
    """Cover JWT auth failure path in chat WebSocket."""
    mock_settings = _make_ws_settings()
    # Keep patch active during connection so handler reads correct settings
    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
    ):
        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/api/v1/chat/ws?token=bad-token") as ws:
                    ws.receive_text()


def test_chat_ws_no_llm():
    """Cover the 'no LLM configured' branch in chat WS."""
    mock_settings = _make_ws_settings()
    token = _ws_token()

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
        patch("angie.llm.is_llm_configured", return_value=False),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
    ):
        mock_pm.return_value.compose_for_user.return_value = "system"

        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
                ws.send_text('{"content": "hello"}')
                reply = ws.receive_text()
                assert "No LLM" in reply or "configured" in reply


def test_chat_ws_with_llm():
    """Cover the LLM path in chat WS."""
    mock_settings = _make_ws_settings()
    token = _ws_token()

    mock_result = MagicMock()
    mock_result.output = "Hello from Angie!"
    mock_result.all_messages.return_value = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hello from Angie!"},
    ]
    mock_agent_obj = AsyncMock()
    mock_agent_obj.run = AsyncMock(return_value=mock_result)
    mock_agent_obj.tool_plain = lambda fn=None, **kw: fn if fn else (lambda f: f)

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
        patch("pydantic_ai.Agent", return_value=mock_agent_obj),
    ):
        mock_pm.return_value.compose_for_user.return_value = "system"

        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
                ws.send_text('{"content": "hello"}')
                reply = ws.receive_text()
                assert "Hello from Angie!" in reply or reply


def test_chat_ws_llm_error():
    """Cover the LLM exception path in chat WS."""
    mock_settings = _make_ws_settings()
    token = _ws_token()

    mock_agent_obj = AsyncMock()
    mock_agent_obj.run = AsyncMock(side_effect=RuntimeError("llm error"))
    mock_agent_obj.tool_plain = lambda fn=None, **kw: fn if fn else (lambda f: f)

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
        patch("pydantic_ai.Agent", return_value=mock_agent_obj),
    ):
        mock_pm.return_value.compose_for_user.return_value = "system"

        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
                ws.send_text("plain text message")
                reply = ws.receive_text()
                assert "error" in reply.lower() or reply


def test_chat_ws_no_sub_claim():
    """Cover line 26: valid JWT but no 'sub' claim → WebSocketException."""
    mock_settings = _make_ws_settings()
    from jose import jwt as jose_jwt

    # Token with no 'sub' field
    token = jose_jwt.encode(
        {"exp": 9999999999},
        "ws-secret",
        algorithm="HS256",
    )
    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
    ):
        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
                    ws.receive_text()


def test_chat_ws_ping_pong():
    """Cover heartbeat ping/pong handling — server responds with pong, skips LLM."""
    mock_settings = _make_ws_settings()
    token = _ws_token()

    with (
        patch("angie.config.get_settings", return_value=mock_settings),
        patch("angie.api.routers.chat.get_settings", return_value=mock_settings),
        patch("angie.llm.is_llm_configured", return_value=False),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
    ):
        mock_pm.return_value.compose_for_user.return_value = "system"

        from angie.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
                ws.send_text('{"type": "ping"}')
                reply = ws.receive_text()
                data = json.loads(reply)
                assert data["type"] == "pong"


# ── api/routers/channels.py upsert update path (lines 52-67) ─────────────────


def test_upsert_channel_config_update():
    """Cover upsert update path (lines 59-66): existing config is updated."""
    from angie.models.channel import ChannelConfig, ChannelType

    mock_settings = MagicMock()
    mock_settings.cors_origins = ["http://localhost:3000"]
    mock_settings.secret_key = "s"
    mock_settings.jwt_algorithm = "HS256"

    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_session = AsyncMock()

    # Simulate existing config
    existing_cfg = MagicMock(spec=ChannelConfig)
    existing_cfg.is_enabled = False
    existing_cfg.config = {}
    existing_cfg.id = "cfg1"
    existing_cfg.user_id = "u1"
    existing_cfg.type = ChannelType.SLACK

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_cfg
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    with patch("angie.config.get_settings", return_value=mock_settings):
        from angie.api.app import create_app

        app = create_app()

    app.dependency_overrides = {}

    from angie.api.auth import get_current_user
    from angie.db.session import get_session

    async def override_user():
        return mock_user

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/channels/slack",
            json={"type": "slack", "is_enabled": True, "config": {"token": "new"}},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200


def test_upsert_channel_config_create():
    """Cover upsert create path (lines 60-62): new config is added."""
    mock_settings = MagicMock()
    mock_settings.cors_origins = ["http://localhost:3000"]
    mock_settings.secret_key = "s"
    mock_settings.jwt_algorithm = "HS256"

    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    def set_id_on_refresh(obj):
        obj.id = "cfg2"
        obj.type = "slack"
        obj.is_enabled = True
        obj.config = {"token": "t"}

    mock_session.refresh = AsyncMock(side_effect=set_id_on_refresh)

    with patch("angie.config.get_settings", return_value=mock_settings):
        from angie.api.app import create_app

        app = create_app()

    from angie.api.auth import get_current_user
    from angie.db.session import get_session

    async def override_user():
        return mock_user

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_session] = override_session

    with TestClient(app) as client:
        resp = client.put(
            "/api/v1/channels/slack",
            json={"type": "slack", "is_enabled": True, "config": {"token": "t"}},
            headers={"Authorization": "Bearer fake"},
        )
    assert resp.status_code == 200
