"""Tests for agent tool functions and execute() paths."""

from unittest.mock import AsyncMock, MagicMock, patch

# ── GmailAgent ────────────────────────────────────────────────────────────────


async def test_gmail_execute_error():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    with patch.object(agent, "_build_service", side_effect=RuntimeError("auth error")):
        result = await agent.execute({"input_data": {"intent": "list emails"}})

    assert "error" in result


def test_gmail_tool_list_messages():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}],
        "resultSizeEstimate": 1,
    }
    msg_detail = {
        "payload": {
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "2025-01-01"},
            ]
        }
    }
    mock_svc.users().messages().get().execute.return_value = msg_detail

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_messages"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx, query="is:unread")

    assert "messages" in result
    assert result["messages"][0]["from"] == "sender@example.com"


def test_gmail_tool_send_message():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().send().execute.return_value = {"id": "sent-id-1"}

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["send_message"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx, to="test@example.com", subject="Hi", body="Hello")

    assert result["sent"] is True


def test_gmail_tool_trash_message():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["trash_message"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx, message_id="msg1")

    assert result["trashed"] is True


def test_gmail_tool_mark_message_read():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["mark_message_read"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx, message_id="msg1")

    assert result["marked_read"] is True


# ── SpamAgent ─────────────────────────────────────────────────────────────────


async def test_spam_agent_scan():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    mock_gmail_result = {
        "messages": [
            {"id": "msg1", "subject": "Win free money now!", "from": "spammer@evil.com"},
            {"id": "msg2", "subject": "Hello friend", "from": "friend@nice.com"},
        ]
    }
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["scan_for_spam"]

    with patch("angie.agents.email.gmail.GmailAgent") as mock_gmail_cls:
        mock_inst = AsyncMock()
        mock_inst.execute.return_value = mock_gmail_result
        mock_gmail_cls.return_value = mock_inst
        result = await tool.function()

    assert "spam_found" in result
    assert result["spam_found"] >= 1  # "free money" matches


async def test_spam_agent_scan_error():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["scan_for_spam"]

    with patch("angie.agents.email.gmail.GmailAgent", side_effect=RuntimeError("fail")):
        result = await tool.function()

    assert "error" in result


async def test_spam_agent_delete():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["delete_spam_messages"]

    with patch("angie.agents.email.gmail.GmailAgent") as mock_gmail_cls:
        mock_inst = AsyncMock()
        mock_inst.execute.return_value = {"trashed": True}
        mock_gmail_cls.return_value = mock_inst
        result = await tool.function(message_ids=["msg1", "msg2"])

    assert result["trashed"] == 2


async def test_spam_agent_unknown():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    result = await agent.execute({"input_data": {"action": "unknown_spam"}})
    assert "error" in result


# ── EmailCorrespondenceAgent ──────────────────────────────────────────────────


async def test_correspondence_draft_no_body():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    with patch("angie.llm.is_llm_configured", return_value=False):
        result = await agent.execute({"input_data": {"action": "draft_reply", "email_body": ""}})
    assert "error" in result


async def test_correspondence_draft_no_llm():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    with patch("angie.llm.is_llm_configured", return_value=False):
        result = await agent.execute(
            {"input_data": {"action": "draft_reply", "email_body": "Hello"}}
        )

    assert "error" in result


async def test_correspondence_draft_success():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    mock_result = MagicMock(output="Draft reply text")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch.object(agent, "_get_agent", return_value=mock_pai),
    ):
        result = await agent.execute(
            {
                "input_data": {
                    "email_body": "Original email",
                    "tone": "casual",
                }
            }
        )

    assert result["draft"] == "Draft reply text"
    assert result["tone"] == "casual"


async def test_correspondence_send_reply_tool():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["send_email_reply"]

    with patch("angie.agents.email.gmail.GmailAgent") as mock_gmail_cls:
        mock_gmail = AsyncMock()
        mock_gmail.execute.return_value = {"sent": True}
        mock_gmail_cls.return_value = mock_gmail
        result = await tool.function(to="sender@example.com", subject="Re: Test", body="Dear sir,")

    assert result["sent"] is True


async def test_correspondence_unknown():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    mock_result = MagicMock(output="I can help draft emails.")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
        patch.object(agent, "_get_agent", return_value=mock_pai),
    ):
        result = await agent.execute({"input_data": {"action": "unknown"}})
    assert "draft" in result


# ── SpotifyAgent ──────────────────────────────────────────────────────────────


async def test_spotify_execute_import_error():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()

    with patch("builtins.__import__", side_effect=ImportError("no spotipy")):
        result = await agent.execute({"input_data": {"action": "current"}})

    assert isinstance(result, dict)


def test_spotify_tool_get_current_track_playing():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "is_playing": True,
        "item": {
            "name": "Test Song",
            "artists": [{"name": "Artist 1"}],
            "album": {"name": "Test Album"},
        },
    }

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_current_track"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["playing"] is True
    assert result["track"] == "Test Song"


def test_spotify_tool_get_current_track_not_playing():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_current_track"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["playing"] is False


def test_spotify_tool_pause_music():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["pause_music"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["paused"] is True


def test_spotify_tool_skip_track():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["skip_track"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["skipped"] is True


def test_spotify_tool_previous_track():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["previous_track"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["previous"] is True


def test_spotify_tool_set_volume():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["set_volume"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx, volume=80)

    assert result["volume"] == 80


def test_spotify_tool_play_with_query():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {
        "tracks": {"items": [{"name": "Found Track", "uri": "spotify:track:1"}]}
    }

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["play_music"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx, query="test song")

    assert result["playing"] is True
    assert result["track"] == "Found Track"


def test_spotify_tool_play_no_results():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": []}}

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["play_music"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx, query="nonexistent")

    assert "error" in result


def test_spotify_tool_play_no_query():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["play_music"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx)

    assert result["playing"] is True


def test_spotify_tool_search_tracks():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {
        "tracks": {"items": [{"name": "Track1", "artists": [{"name": "Artist"}], "uri": "uri1"}]}
    }

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["search_tracks"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_sp
    result = tool.function(mock_ctx, query="test")

    assert "results" in result
    assert len(result["results"]) == 1


# ── HueAgent ──────────────────────────────────────────────────────────────────


async def test_hue_no_bridge_ip():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    with patch.dict("os.environ", {"HUE_BRIDGE_IP": ""}):
        result = await agent.execute({"input_data": {"action": "list"}})

    assert "error" in result
    assert "HUE_BRIDGE_IP" in result["error"]


async def test_hue_execute_error():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    with (
        patch.dict("os.environ", {"HUE_BRIDGE_IP": "192.168.1.1"}),
        patch("phue.Bridge", side_effect=RuntimeError("no bridge")),
    ):
        result = await agent.execute({"input_data": {"action": "list"}})

    assert "error" in result


def test_hue_tool_list_lights():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()
    mock_light = MagicMock()
    mock_light.on = True
    mock_bridge.get_light_objects.return_value = {"Living Room": mock_light}

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_lights"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx)

    assert "lights" in result
    assert result["lights"][0]["name"] == "Living Room"


def test_hue_tool_turn_on_named():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_on_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, light_name="Bedroom")

    assert result["on"] is True
    mock_bridge.set_light.assert_called_with("Bedroom", "on", True)


def test_hue_tool_turn_on_all():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_on_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx)

    assert result["on"] is True
    mock_bridge.set_group.assert_called_with(0, "on", True)


def test_hue_tool_turn_off_named():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_off_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, light_name="Kitchen")

    assert result["off"] is True
    mock_bridge.set_light.assert_called_with("Kitchen", "on", False)


def test_hue_tool_turn_off_all():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_off_light"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx)

    assert result["off"] is True
    mock_bridge.set_group.assert_called_with(0, "on", False)


def test_hue_tool_set_brightness_named():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["set_brightness"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, brightness=200, light_name="Lamp")

    assert result["brightness"] == 200
    mock_bridge.set_light.assert_called_with("Lamp", "bri", 200)


def test_hue_tool_set_brightness_all():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["set_brightness"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, brightness=128)

    assert result["brightness"] == 128
    mock_bridge.set_group.assert_called_with(0, "bri", 128)


def test_hue_tool_set_color_named():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["set_color"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, hue=10000, saturation=200, light_name="Desk")

    assert result["color_set"] is True
    mock_bridge.set_light.assert_called_with("Desk", {"hue": 10000, "sat": 200})


def test_hue_tool_set_color_all():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["set_color"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_bridge
    result = tool.function(mock_ctx, hue=5000, saturation=100)

    assert result["color_set"] is True
    mock_bridge.set_group.assert_called_with(0, {"hue": 5000, "sat": 100})


# ── HomeAssistantAgent ────────────────────────────────────────────────────────


async def test_ha_no_config():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    with patch.dict("os.environ", {"HOME_ASSISTANT_URL": "", "HOME_ASSISTANT_TOKEN": ""}):
        result = await agent.execute({"input_data": {"action": "states"}})

    assert "error" in result
    assert "HOME_ASSISTANT_URL" in result["error"]


async def test_ha_tool_get_all_states():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_all_states"]

    mock_resp = AsyncMock()
    mock_resp.json.return_value = [
        {"entity_id": "light.bedroom", "state": "on"},
        {"entity_id": "sensor.temp", "state": "22"},
    ]

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.deps = {"url": "http://ha.local", "token": "tok"}

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await tool.function(mock_ctx)

    assert "entities" in result
    assert len(result["entities"]) == 2


async def test_ha_tool_get_entity_state():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_entity_state"]

    mock_resp = AsyncMock()
    mock_resp.json.return_value = {"entity_id": "light.bedroom", "state": "on"}

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.deps = {"url": "http://ha.local", "token": "tok"}

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await tool.function(mock_ctx, entity_id="light.bedroom")

    assert result["state"] == "on"


async def test_ha_tool_call_service():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["call_service"]

    mock_resp = AsyncMock()
    mock_resp.json.return_value = []

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.deps = {"url": "http://ha.local", "token": "tok"}

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await tool.function(
            mock_ctx, domain="light", service="turn_on", entity_id="light.bedroom"
        )

    assert result["called"] is True


async def test_ha_tool_turn_on_entity():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_on_entity"]

    mock_resp = AsyncMock()
    mock_resp.json.return_value = {}

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.deps = {"url": "http://ha.local", "token": "tok"}

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await tool.function(mock_ctx, entity_id="light.x")

    assert result["on"] is True


async def test_ha_tool_turn_off_entity():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["turn_off_entity"]

    mock_resp = AsyncMock()
    mock_resp.json.return_value = {}

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_ctx = MagicMock()
    mock_ctx.deps = {"url": "http://ha.local", "token": "tok"}

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await tool.function(mock_ctx, entity_id="light.x")

    assert result["off"] is True


# ── GoogleCalendarAgent ───────────────────────────────────────────────────────


async def test_gcal_execute_error():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    with patch.object(agent, "_build_service", side_effect=RuntimeError("gcal error")):
        result = await agent.execute({"input_data": {"action": "list"}})

    assert "error" in result


def test_gcal_tool_list_events():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()
    mock_svc.events().list().execute.return_value = {
        "items": [
            {
                "id": "evt1",
                "summary": "Meeting",
                "start": {"dateTime": "2025-01-01T10:00:00Z"},
                "end": {"dateTime": "2025-01-01T11:00:00Z"},
            }
        ]
    }

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_upcoming_events"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx)

    assert "events" in result
    assert result["events"][0]["summary"] == "Meeting"


def test_gcal_tool_create_event():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()
    mock_svc.events().insert().execute.return_value = {
        "id": "new-evt",
        "htmlLink": "http://cal.link",
    }

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["create_event"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(
        mock_ctx,
        summary="New Meeting",
        start="2025-01-01T10:00:00Z",
        end="2025-01-01T11:00:00Z",
    )

    assert result["created"] is True
    assert result["event_id"] == "new-evt"


def test_gcal_tool_delete_event():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["delete_event"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_svc
    result = tool.function(mock_ctx, event_id="evt1")

    assert result["deleted"] is True


# ── GitHubAgent ───────────────────────────────────────────────────────────────


async def test_github_execute_import_error():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    with patch("github.Github", side_effect=RuntimeError("auth error")):
        result = await agent.execute({"input_data": {"action": "list_repos"}})

    assert isinstance(result, dict)
    assert "error" in result


def test_github_tool_list_repositories():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_repo = MagicMock()
    mock_repo.full_name = "user/repo1"
    mock_repo.private = False
    mock_g.get_user().get_repos.return_value = [mock_repo]

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_repositories"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_g
    result = tool.function(mock_ctx)

    assert isinstance(result, list)
    assert result[0]["name"] == "user/repo1"


def test_github_tool_list_pull_requests():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_pr = MagicMock()
    mock_pr.number = 1
    mock_pr.title = "Test PR"
    mock_pr.state = "open"
    mock_pr.user.login = "user1"
    mock_g.get_repo.return_value.get_pulls.return_value = [mock_pr]

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_pull_requests"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_g
    result = tool.function(mock_ctx, repo="user/repo")

    assert isinstance(result, list)
    assert result[0]["number"] == 1


def test_github_tool_list_issues():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 5
    mock_issue.title = "Bug"
    mock_issue.state = "open"
    mock_issue.user.login = "user2"
    mock_g.get_repo.return_value.get_issues.return_value = [mock_issue]

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["list_issues"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_g
    result = tool.function(mock_ctx, repo="user/repo")

    assert isinstance(result, list)
    assert result[0]["number"] == 5


def test_github_tool_create_issue():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 10
    mock_issue.html_url = "http://github.com/issue/10"
    mock_g.get_repo.return_value.create_issue.return_value = mock_issue

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["create_issue"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_g
    result = tool.function(mock_ctx, repo="user/repo", title="New issue", body="Details")

    assert result["created"] is True


def test_github_tool_get_repository():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_repo = MagicMock()
    mock_repo.full_name = "user/repo"
    mock_repo.description = "A repo"
    mock_repo.stargazers_count = 42
    mock_repo.forks_count = 5
    mock_repo.open_issues_count = 3
    mock_repo.default_branch = "main"
    mock_g.get_repo.return_value = mock_repo

    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_repository"]
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_g
    result = tool.function(mock_ctx, repo="user/repo")

    assert result["stars"] == 42


# ── UbiquitiAgent ─────────────────────────────────────────────────────────────


async def test_ubiquiti_execute():
    from angie.agents.networking.ubiquiti import UbiquitiAgent

    agent = UbiquitiAgent()
    result = await agent.execute({"title": "get wifi clients", "input_data": {}})
    assert result["status"] == "not_implemented"
    assert result["agent"] == "ubiquiti"


# ── RemindersAgent ────────────────────────────────────────────────────────────


async def test_reminders_create_reminder():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["create_reminder"]
    with _patch(
        "angie.agents.productivity.reminders._create_reminder_in_db", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {"created": True, "reminder_id": "r1", "message": "Call Mom"}
        result = await tool.function(message="Call Mom", when="tomorrow at 3pm")

    assert result["created"] is True
    assert result["message"] == "Call Mom"


async def test_reminders_create_reminder_bad_date():
    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["create_reminder"]
    result = await tool.function(message="Test", when="not a real date xyzzy")
    assert "error" in result


async def test_reminders_create_recurring():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["create_recurring"]
    with _patch(
        "angie.agents.productivity.reminders._create_recurring_in_db", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {
            "created": True,
            "reminder_id": "r2",
            "message": "Submit timesheet",
            "cron_expression": "0 15 * * 5",
            "is_recurring": True,
        }
        result = await tool.function(message="Submit timesheet", cron_expr="0 15 * * 5")

    assert result["created"] is True
    assert result["is_recurring"] is True


async def test_reminders_create_recurring_invalid_cron():
    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["create_recurring"]
    result = await tool.function(message="Test", cron_expr="bad cron")
    assert "error" in result


async def test_reminders_list_reminders():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["list_reminders"]
    with _patch(
        "angie.agents.productivity.reminders._list_reminders_from_db", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {"reminders": []}
        result = await tool.function()

    assert "reminders" in result


async def test_reminders_complete_reminder():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["complete_reminder"]
    with _patch(
        "angie.agents.productivity.reminders._update_reminder_status", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {"updated": True, "reminder_id": "r1", "status": "delivered"}
        result = await tool.function(reminder_id="r1")

    assert result["updated"] is True


async def test_reminders_cancel_reminder():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["cancel_reminder"]
    with _patch(
        "angie.agents.productivity.reminders._cancel_reminder_in_db", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {"cancelled": True, "reminder_id": "r1"}
        result = await tool.function(reminder_id="r1")

    assert result["cancelled"] is True


async def test_reminders_create_todo():
    from unittest.mock import patch as _patch

    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="user-1")

    tool = pa._function_toolset.tools["create_todo"]
    with _patch(
        "angie.agents.productivity.reminders._create_reminder_in_db", new_callable=AsyncMock
    ) as mock_db:
        mock_db.return_value = {
            "created": True,
            "reminder_id": "r3",
            "message": "[NORMAL] Buy groceries",
        }
        result = await tool.function(title="Buy groceries")

    assert result["created"] is True


async def test_reminders_no_user_id():
    from angie.agents.productivity.reminders import RemindersAgent

    agent = RemindersAgent()
    pa = agent.build_pydantic_agent(user_id="")

    tool = pa._function_toolset.tools["create_reminder"]
    result = await tool.function(message="Test", when="tomorrow")
    assert result["error"] == "user_id not available in task context"


# ── SoftwareDeveloperAgent ────────────────────────────────────────────────────


def test_software_dev_parse_issue_url():
    from angie.agents.dev.software_dev import _parse_issue_url

    owner, repo, number = _parse_issue_url("https://github.com/owner/repo/issues/42")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 42


def test_software_dev_parse_issue_url_shorthand():
    from angie.agents.dev.software_dev import _parse_issue_url

    owner, repo, number = _parse_issue_url("owner/repo#7")
    assert owner == "owner"
    assert repo == "repo"
    assert number == 7


def test_software_dev_parse_issue_url_invalid():
    import pytest

    from angie.agents.dev.software_dev import _parse_issue_url

    with pytest.raises(ValueError, match="Could not parse"):
        _parse_issue_url("not a valid url")


def test_software_dev_fetch_issue():
    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["fetch_issue"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(github_token="test-token")

    mock_issue = MagicMock()
    mock_issue.title = "Fix login bug"
    mock_issue.body = "Login is broken"
    mock_issue.labels = []
    mock_comment = MagicMock()
    mock_comment.user.login = "reviewer"
    mock_comment.body = "Please fix ASAP"
    mock_issue.get_comments.return_value = [mock_comment]

    mock_repo = MagicMock()
    mock_repo.default_branch = "main"
    mock_repo.get_issue.return_value = mock_issue

    with patch("github.Github") as mock_gh:
        mock_gh.return_value.get_repo.return_value = mock_repo
        result = tool.function(mock_ctx, issue_url="https://github.com/owner/repo/issues/42")

    assert result["title"] == "Fix login bug"
    assert result["number"] == 42
    assert len(result["comments"]) == 1


def test_software_dev_create_branch(tmp_path):
    import subprocess

    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True, check=True
    )
    (repo_dir / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, capture_output=True, check=True)

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["create_branch"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(repo_dir=repo_dir)
    result = tool.function(mock_ctx, branch_name="angie/issue-42-fix-login")

    assert result["created"] is True
    assert result["branch"] == "angie/issue-42-fix-login"


def test_software_dev_read_file(tmp_path):
    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "test.py").write_text("print('hello')")

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["read_file"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(repo_dir=repo_dir)
    result = tool.function(mock_ctx, path="test.py")

    assert result["content"] == "print('hello')"


def test_software_dev_write_file(tmp_path):
    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["write_file"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(repo_dir=repo_dir)
    result = tool.function(mock_ctx, path="new_file.py", content="print('world')")

    assert result["written"] is True
    assert (repo_dir / "new_file.py").read_text() == "print('world')"


def test_software_dev_list_directory(tmp_path):
    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "file.py").write_text("")
    (repo_dir / "subdir").mkdir()

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["list_directory"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(repo_dir=repo_dir)
    result = tool.function(mock_ctx, path=".")

    names = [e["name"] for e in result["entries"]]
    assert "file.py" in names
    assert "subdir" in names


def test_software_dev_run_command_blocked():
    from pathlib import Path

    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["run_command"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(repo_dir=Path("/tmp"))
    result = tool.function(mock_ctx, command="rm -rf /")

    assert "error" in result
    assert "blocked" in result["error"]


def test_software_dev_create_pr():
    from angie.agents.dev.software_dev import SoftwareDevDeps, SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()

    tool = pa._function_toolset.tools["create_pull_request"]
    mock_ctx = MagicMock()
    mock_ctx.deps = SoftwareDevDeps(github_token="test-token")

    mock_pr = MagicMock()
    mock_pr.number = 99
    mock_pr.html_url = "https://github.com/owner/repo/pull/99"
    mock_pr.title = "Fix login bug"

    with patch("github.Github") as mock_gh:
        mock_repo = MagicMock()
        mock_repo.default_branch = "main"
        mock_repo.create_pull.return_value = mock_pr
        mock_gh.return_value.get_repo.return_value = mock_repo
        result = tool.function(
            mock_ctx,
            repo="owner/repo",
            branch="angie/issue-42",
            title="Fix login bug",
            body="Fixes the login issue",
            issue_number=42,
        )

    assert result["created"] is True
    assert result["pr_number"] == 99
    assert "Closes #42" in mock_repo.create_pull.call_args[1]["body"]
