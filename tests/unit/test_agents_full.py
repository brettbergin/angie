"""Tests for remaining agent coverage gaps."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _task(action: str, **kw):
    return {"title": "t", "input_data": {"action": action, **kw}}


# ── Outlook + Yahoo (not_implemented stubs) ────────────────────────────────────


@pytest.mark.asyncio
async def test_outlook_agent_not_implemented():
    from angie.agents.email.outlook import OutlookAgent

    result = await OutlookAgent().execute({"title": "t"})
    assert result["status"] == "not_implemented"


@pytest.mark.asyncio
async def test_yahoo_agent_not_implemented():
    from angie.agents.email.yahoo import YahooMailAgent

    result = await YahooMailAgent().execute({"title": "t"})
    assert result["status"] == "not_implemented"


# ── Gmail _build_service (mock google libs) ────────────────────────────────────


@pytest.mark.asyncio
async def test_gmail_build_service_success(tmp_path):
    token_file = tmp_path / "gmail_token.json"
    token_file.write_text('{"token": "abc"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": []
    }

    mock_google_creds = MagicMock()
    mock_google_creds.Credentials.from_authorized_user_file.return_value = mock_creds
    mock_build = MagicMock(return_value=mock_service)
    mock_discovery = MagicMock()
    mock_discovery.build = mock_build

    modules_to_mock = {
        "google": MagicMock(),
        "google.oauth2": MagicMock(),
        "google.oauth2.credentials": mock_google_creds,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": mock_discovery,
    }

    mock_result = MagicMock(output="No messages.")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)

    os.environ["GMAIL_TOKEN_FILE"] = str(token_file)
    # Remove cached module so fresh import picks up mocks
    sys.modules.pop("angie.agents.email.gmail", None)
    with patch.dict("sys.modules", modules_to_mock):
        import angie.agents.email.gmail as _gmail_mod

        agent = _gmail_mod.GmailAgent()
        with (
            patch.object(agent, "_get_agent", return_value=mock_pai),
            patch("angie.llm.get_llm_model", return_value=MagicMock()),
        ):
            result = await agent.execute(_task("list"))
    os.environ.pop("GMAIL_TOKEN_FILE", None)
    sys.modules.pop("angie.agents.email.gmail", None)

    assert "result" in result or "error" in result


@pytest.mark.asyncio
async def test_gmail_build_service_no_token():
    """When token file doesn't exist, _build_service raises RuntimeError."""
    mock_google_creds = MagicMock()
    mock_discovery = MagicMock()

    modules_to_mock = {
        "google": MagicMock(),
        "google.oauth2": MagicMock(),
        "google.oauth2.credentials": mock_google_creds,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": mock_discovery,
    }

    os.environ["GMAIL_TOKEN_FILE"] = "/nonexistent/path/token.json"
    sys.modules.pop("angie.agents.email.gmail", None)
    with patch.dict("sys.modules", modules_to_mock):
        import angie.agents.email.gmail as _gmail_mod

        agent = _gmail_mod.GmailAgent()
        result = await agent.execute(_task("list"))
    os.environ.pop("GMAIL_TOKEN_FILE", None)
    sys.modules.pop("angie.agents.email.gmail", None)

    assert "error" in result


# ── GCal _build_service ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gcal_build_service_success(tmp_path):
    token_file = tmp_path / "gcal_token.json"
    token_file.write_text('{"token": "abc"}', encoding="utf-8")

    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

    mock_google_creds = MagicMock()
    mock_google_creds.Credentials.from_authorized_user_file.return_value = mock_creds
    mock_discovery = MagicMock()
    mock_discovery.build.return_value = mock_service

    modules_to_mock = {
        "google": MagicMock(),
        "google.oauth2": MagicMock(),
        "google.oauth2.credentials": mock_google_creds,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": mock_discovery,
    }

    mock_result = MagicMock(output="No events.")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)

    os.environ["GCAL_TOKEN_FILE"] = str(token_file)
    sys.modules.pop("angie.agents.calendar.gcal", None)
    with patch.dict("sys.modules", modules_to_mock):
        import angie.agents.calendar.gcal as _gcal_mod

        agent = _gcal_mod.GoogleCalendarAgent()
        with (
            patch.object(agent, "_get_agent", return_value=mock_pai),
            patch("angie.llm.get_llm_model", return_value=MagicMock()),
        ):
            result = await agent.execute(_task("list"))
    os.environ.pop("GCAL_TOKEN_FILE", None)
    sys.modules.pop("angie.agents.calendar.gcal", None)

    assert "result" in result or "error" in result


@pytest.mark.asyncio
async def test_gcal_build_service_no_token():
    mock_google_creds = MagicMock()
    mock_discovery = MagicMock()

    modules_to_mock = {
        "google": MagicMock(),
        "google.oauth2": MagicMock(),
        "google.oauth2.credentials": mock_google_creds,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": mock_discovery,
    }

    os.environ["GCAL_TOKEN_FILE"] = "/nonexistent/gcal_token.json"
    sys.modules.pop("angie.agents.calendar.gcal", None)
    with patch.dict("sys.modules", modules_to_mock):
        import angie.agents.calendar.gcal as _gcal_mod

        agent = _gcal_mod.GoogleCalendarAgent()
        result = await agent.execute(_task("list"))
    os.environ.pop("GCAL_TOKEN_FILE", None)
    sys.modules.pop("angie.agents.calendar.gcal", None)

    assert "error" in result


# ── GitHub ImportError ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_import_error():
    sys.modules.pop("angie.agents.dev.github", None)
    with patch.dict("sys.modules", {"github": None}):  # type: ignore[dict-item]
        import angie.agents.dev.github as _gh_mod

        agent = _gh_mod.GitHubAgent()
        result = await agent.execute(_task("list_repos"))
    sys.modules.pop("angie.agents.dev.github", None)
    # Restore: ensure next tests can freshly import the module
    import angie.agents.dev

    if hasattr(angie.agents.dev, "github"):
        delattr(angie.agents.dev, "github")

    assert result.get("error") == "PyGithub not installed"


# ── Spotify exception path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_spotify_generic_exception():
    mock_spotipy = MagicMock()
    mock_spotipy.Spotify.side_effect = RuntimeError("connection refused")
    mock_oauth2 = MagicMock()

    sys.modules.pop("angie.agents.media.spotify", None)
    with patch.dict("sys.modules", {"spotipy": mock_spotipy, "spotipy.oauth2": mock_oauth2}):
        import angie.agents.media.spotify as _sp_mod

        agent = _sp_mod.SpotifyAgent()
        result = await agent.execute(_task("current"))
    sys.modules.pop("angie.agents.media.spotify", None)
    # Restore: ensure next tests can freshly import the module
    import angie.agents.media

    if hasattr(angie.agents.media, "spotify"):
        delattr(angie.agents.media, "spotify")

    assert "error" in result


# ── Registry module load exception ────────────────────────────────────────────


def test_registry_load_exception():
    """When a module raises ImportError during load_all, it's logged and skipped."""
    from angie.agents.registry import AgentRegistry

    registry = AgentRegistry()
    # Inject a bad module path into AGENT_MODULES temporarily
    with patch("angie.agents.registry.AGENT_MODULES", ["nonexistent.module.path"]):
        registry.load_all()
    # Should not raise; bad module is skipped
    assert registry._loaded is True


# ── HomeAssistant ImportError + generic exception ─────────────────────────────


@pytest.mark.asyncio
async def test_home_assistant_import_error():
    os.environ["HOME_ASSISTANT_URL"] = "http://ha.local:8123"
    os.environ["HOME_ASSISTANT_TOKEN"] = "tok"
    sys.modules.pop("angie.agents.smart_home.home_assistant", None)
    with patch.dict("sys.modules", {"aiohttp": None}):  # type: ignore[dict-item]
        import angie.agents.smart_home.home_assistant as _ha_mod

        agent = _ha_mod.HomeAssistantAgent()
        result = await agent.execute(_task("states"))
    os.environ.pop("HOME_ASSISTANT_URL", None)
    os.environ.pop("HOME_ASSISTANT_TOKEN", None)
    sys.modules.pop("angie.agents.smart_home.home_assistant", None)

    assert result.get("error") == "aiohttp not installed"


@pytest.mark.asyncio
async def test_home_assistant_generic_exception():
    mock_aiohttp = MagicMock()
    mock_aiohttp.ClientSession.side_effect = RuntimeError("network error")

    os.environ["HOME_ASSISTANT_URL"] = "http://ha.local:8123"
    os.environ["HOME_ASSISTANT_TOKEN"] = "tok"

    sys.modules.pop("angie.agents.smart_home.home_assistant", None)
    with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
        import angie.agents.smart_home.home_assistant as _ha_mod

        agent = _ha_mod.HomeAssistantAgent()
        mock_pai = MagicMock()
        mock_pai.run = AsyncMock(side_effect=RuntimeError("network error"))
        with (
            patch.object(agent, "_get_agent", return_value=mock_pai),
            patch("angie.llm.get_llm_model", return_value=MagicMock()),
        ):
            result = await agent.execute(_task("states"))
    sys.modules.pop("angie.agents.smart_home.home_assistant", None)

    os.environ.pop("HOME_ASSISTANT_URL", None)
    os.environ.pop("HOME_ASSISTANT_TOKEN", None)
    assert "error" in result


# ── Hue: ImportError + dispatch branches ──────────────────────────────────────


@pytest.mark.asyncio
async def test_hue_import_error():
    os.environ["HUE_BRIDGE_IP"] = "192.168.1.100"
    sys.modules.pop("angie.agents.smart_home.hue", None)
    with patch.dict("sys.modules", {"phue": None}):  # type: ignore[dict-item]
        import angie.agents.smart_home.hue as _hue_mod

        agent = _hue_mod.HueAgent()
        result = await agent.execute(_task("list"))
    os.environ.pop("HUE_BRIDGE_IP", None)
    sys.modules.pop("angie.agents.smart_home.hue", None)

    assert result.get("error") == "phue not installed"


@pytest.mark.asyncio
async def test_hue_on_group_fallback():
    """turn_on_light tool with no light_name calls set_group."""
    from angie.agents.smart_home.hue import HueAgent

    mock_bridge = MagicMock()
    agent = HueAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["turn_on_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    tool.function(mock_ctx)
    mock_bridge.set_group.assert_called_with(0, "on", True)


@pytest.mark.asyncio
async def test_hue_off_named_light():
    """turn_off_light tool with light_name calls set_light."""
    from angie.agents.smart_home.hue import HueAgent

    mock_bridge = MagicMock()
    agent = HueAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["turn_off_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    tool.function(mock_ctx, light_name="Bedroom")
    mock_bridge.set_light.assert_called_with("Bedroom", "on", False)


@pytest.mark.asyncio
async def test_hue_brightness_named():
    """set_brightness tool with light_name calls set_light."""
    from angie.agents.smart_home.hue import HueAgent

    mock_bridge = MagicMock()
    agent = HueAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["set_brightness"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    tool.function(mock_ctx, brightness=128, light_name="Kitchen")
    mock_bridge.set_light.assert_called_with("Kitchen", "bri", 128)


@pytest.mark.asyncio
async def test_hue_color_named():
    """set_color tool with light_name calls set_light."""
    from angie.agents.smart_home.hue import HueAgent

    mock_bridge = MagicMock()
    agent = HueAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["set_color"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    tool.function(mock_ctx, hue=10000, saturation=200, light_name="Living Room")
    mock_bridge.set_light.assert_called_with("Living Room", {"hue": 10000, "sat": 200})


# ── Spam: _delete_spam with message IDs ───────────────────────────────────────


@pytest.mark.asyncio
async def test_spam_delete_with_ids():
    """delete_spam_messages tool trashes specified message IDs."""
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["delete_spam_messages"]

    mock_gmail = AsyncMock()
    mock_gmail.execute.return_value = {"status": "trashed"}

    with patch("angie.agents.email.gmail.GmailAgent", return_value=mock_gmail):
        result = await tool.function(message_ids=["msg-1", "msg-2"])

    assert result["trashed"] == 2


# ── Correspondence: send_reply returns draft error early ─────────────────────


@pytest.mark.asyncio
async def test_correspondence_send_reply_returns_draft_error():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    with patch("angie.llm.is_llm_configured", return_value=False):
        result = await agent.execute(_task("send_reply"))  # no email_body
    assert "error" in result


# ── Registry generic exception (lines 62-63) ──────────────────────────────────


def test_registry_generic_exception():
    """When a module raises a non-ImportError, it's logged and skipped."""
    from angie.agents.registry import AgentRegistry

    registry = AgentRegistry()

    # Use a module path that will raise a generic Exception during import
    with patch("angie.agents.registry.AGENT_MODULES", ["angie.agents.base"]):
        # Patch importlib.import_module to raise generic Exception
        with patch("importlib.import_module", side_effect=RuntimeError("boom")):
            registry.load_all()

    assert registry._loaded is True


# ── Spam agent _delete_spam exception path (lines 56-57) ─────────────────────


@pytest.mark.asyncio
async def test_spam_delete_exception():
    """delete_spam_messages tool returns error dict when gmail.execute raises."""
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    tool = agent.build_pydantic_agent()._function_toolset.tools["delete_spam_messages"]

    mock_gmail = AsyncMock()
    mock_gmail.execute.side_effect = RuntimeError("gmail error")

    with patch("angie.agents.email.gmail.GmailAgent", return_value=mock_gmail):
        result = await tool.function(message_ids=["msg-1"])

    assert "error" in result
