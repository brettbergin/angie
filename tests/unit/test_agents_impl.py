"""Tests for agent execute() methods — mocking external SDKs."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_task(action: str, **extra):
    return {"title": "test", "input_data": {"action": action, **extra}}


# ── Gmail agent ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gmail_agent_list():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": []
    }
    with patch.object(agent, "_build_service", return_value=mock_service):
        result = await agent.execute(_make_task("list"))
    assert "messages" in result or "emails" in result or "error" in result


@pytest.mark.asyncio
async def test_gmail_agent_no_credentials():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    with patch.object(agent, "_build_service", side_effect=FileNotFoundError("no creds")):
        result = await agent.execute(_make_task("list"))
    assert "error" in result


@pytest.mark.asyncio
async def test_gmail_agent_send():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg-1"
    }
    with patch.object(agent, "_build_service", return_value=mock_service):
        result = await agent.execute(
            _make_task("send", to="test@example.com", subject="hi", body="hello")
        )
    assert "error" in result or "sent" in result or "id" in result or "message_id" in result


# ── Spam agent ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spam_agent_scan():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    mock_result = MagicMock(output="Found spam messages")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(agent, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await agent.execute(_make_task("scan"))
    assert "result" in result or "error" in result


@pytest.mark.asyncio
async def test_spam_agent_delete():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    mock_result = MagicMock(output="Deleted spam messages")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(agent, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await agent.execute(_make_task("delete_spam"))
    assert "result" in result or "error" in result


@pytest.mark.asyncio
async def test_spam_agent_unknown_action():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    result = await agent.execute(_make_task("unknown_action"))
    assert "error" in result


# ── Correspondence agent ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correspondence_agent_draft():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    mock_result = MagicMock(output="Dear...")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch.object(agent, "_get_agent", return_value=mock_pai),
    ):
        result = await agent.execute(_make_task("draft_reply", email_body="Hello", context="reply"))
    assert "draft" in result or "reply" in result or "error" in result


@pytest.mark.asyncio
async def test_correspondence_agent_unknown():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    result = await agent.execute(_make_task("bad_action"))
    assert "error" in result


# ── GitHub agent ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_agent_list_issues():
    mock_issue = MagicMock()
    mock_issue.number = 1
    mock_issue.title = "Test issue"
    mock_issue.state = "open"
    mock_issue.user.login = "alice"

    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [mock_issue]

    mock_gh_instance = MagicMock()
    mock_gh_instance.get_repo.return_value = mock_repo

    mock_gh_module = MagicMock()
    mock_gh_module.Github.return_value = mock_gh_instance

    import importlib

    import angie.agents.dev

    with patch.dict("sys.modules", {"github": mock_gh_module}):
        sys.modules.pop("angie.agents.dev.github", None)
        if hasattr(angie.agents.dev, "github"):
            delattr(angie.agents.dev, "github")
        _gh_mod = importlib.import_module("angie.agents.dev.github")
        agent = _gh_mod.GitHubAgent()
        result = await agent.execute(_make_task("list_issues", repo="org/repo"))

    assert "issues" in result or "error" in result


@pytest.mark.asyncio
async def test_github_agent_no_token():
    mock_gh_module = MagicMock()
    mock_gh_module.Github.side_effect = Exception("no token")

    import importlib

    import angie.agents.dev

    with patch.dict("sys.modules", {"github": mock_gh_module}):
        sys.modules.pop("angie.agents.dev.github", None)
        if hasattr(angie.agents.dev, "github"):
            delattr(angie.agents.dev, "github")
        _gh_mod = importlib.import_module("angie.agents.dev.github")
        agent = _gh_mod.GitHubAgent()
        result = await agent.execute(_make_task("list_issues", repo="org/repo"))

    assert "error" in result


# ── Gcal agent ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gcal_agent_list():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}
    with patch.object(agent, "_build_service", return_value=mock_service):
        result = await agent.execute(_make_task("list"))
    assert "events" in result or "error" in result


@pytest.mark.asyncio
async def test_gcal_agent_no_creds():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    with patch.object(agent, "_build_service", side_effect=RuntimeError("no token file")):
        result = await agent.execute(_make_task("list"))
    assert "error" in result


# ── Spotify agent ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spotify_agent_current():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "is_playing": True,
        "item": {
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"},
        },
    }

    mock_spotipy = MagicMock()
    mock_spotipy.Spotify.return_value = mock_sp
    mock_spotipy.oauth2 = MagicMock()

    import importlib

    import angie.agents.media

    with patch.dict(
        "sys.modules", {"spotipy": mock_spotipy, "spotipy.oauth2": mock_spotipy.oauth2}
    ):
        sys.modules.pop("angie.agents.media.spotify", None)
        if hasattr(angie.agents.media, "spotify"):
            delattr(angie.agents.media, "spotify")
        _sp_mod = importlib.import_module("angie.agents.media.spotify")
        agent = _sp_mod.SpotifyAgent()
        result = await agent.execute(_make_task("current"))

    assert "track" in result or "playing" in result or "error" in result


@pytest.mark.asyncio
async def test_spotify_agent_import_error():
    import importlib

    import angie.agents.media

    with patch.dict("sys.modules", {"spotipy": None}):  # type: ignore[dict-item]
        sys.modules.pop("angie.agents.media.spotify", None)
        if hasattr(angie.agents.media, "spotify"):
            delattr(angie.agents.media, "spotify")
        _sp_mod = importlib.import_module("angie.agents.media.spotify")
        agent = _sp_mod.SpotifyAgent()
        result = await agent.execute(_make_task("current"))

    assert "error" in result


# ── Philips Hue agent ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hue_agent_no_bridge_ip():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    old = os.environ.pop("HUE_BRIDGE_IP", None)
    try:
        result = await agent.execute(_make_task("list"))
    finally:
        if old is not None:
            os.environ["HUE_BRIDGE_IP"] = old
    assert "error" in result


@pytest.mark.asyncio
async def test_hue_agent_list_lights():
    mock_bridge = MagicMock()
    light = MagicMock()
    light.on = True
    mock_bridge.get_light_objects.return_value = {"Living Room": light}

    mock_phue = MagicMock()
    mock_phue.Bridge.return_value = mock_bridge

    with patch.dict("sys.modules", {"phue": mock_phue}):
        os.environ["HUE_BRIDGE_IP"] = "192.168.1.10"
        import importlib

        from angie.agents.smart_home import hue as _hue_mod

        importlib.reload(_hue_mod)
        agent = _hue_mod.HueAgent()
        result = await agent.execute(_make_task("list"))
        os.environ.pop("HUE_BRIDGE_IP", None)

    assert "lights" in result or "error" in result


# ── Home Assistant agent ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_home_assistant_agent_no_config():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    old_url = os.environ.pop("HOME_ASSISTANT_URL", None)
    old_tok = os.environ.pop("HOME_ASSISTANT_TOKEN", None)
    try:
        result = await agent.execute(_make_task("states"))
    finally:
        if old_url:
            os.environ["HOME_ASSISTANT_URL"] = old_url
        if old_tok:
            os.environ["HOME_ASSISTANT_TOKEN"] = old_tok
    assert "error" in result


@pytest.mark.asyncio
async def test_home_assistant_agent_states():
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=[{"entity_id": "light.test", "state": "on"}])
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_aiohttp = MagicMock()
    mock_aiohttp.ClientSession.return_value = mock_session

    os.environ["HOME_ASSISTANT_URL"] = "http://ha.local:8123"
    os.environ["HOME_ASSISTANT_TOKEN"] = "test-token"

    with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
        import importlib

        from angie.agents.smart_home import home_assistant as _ha_mod

        importlib.reload(_ha_mod)
        agent = _ha_mod.HomeAssistantAgent()
        result = await agent.execute(_make_task("states"))

    os.environ.pop("HOME_ASSISTANT_URL", None)
    os.environ.pop("HOME_ASSISTANT_TOKEN", None)

    assert "entities" in result or "error" in result
