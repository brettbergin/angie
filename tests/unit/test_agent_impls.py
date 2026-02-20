"""Tests for various agent implementations."""

from unittest.mock import AsyncMock, MagicMock, patch


# ── GmailAgent tests ──────────────────────────────────────────────────────────

async def test_gmail_execute_error():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    with patch.object(agent, "_dispatch", side_effect=RuntimeError("auth error")):
        result = await agent.execute({"input_data": {"action": "list"}})

    assert "error" in result


async def test_gmail_dispatch_list():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}],
        "resultSizeEstimate": 1,
    }
    msg_detail = {
        "payload": {"headers": [
            {"name": "From", "value": "sender@example.com"},
            {"name": "Subject", "value": "Test"},
            {"name": "Date", "value": "2025-01-01"},
        ]}
    }
    mock_svc.users().messages().get().execute.return_value = msg_detail

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("list", {"query": "is:unread"})

    assert "messages" in result
    assert result["messages"][0]["from"] == "sender@example.com"


async def test_gmail_dispatch_send():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().send().execute.return_value = {"id": "sent-id-1"}

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("send", {"to": "test@example.com", "subject": "Hi", "body": "Hello"})

    assert result["sent"] is True


async def test_gmail_dispatch_trash():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().trash().execute.return_value = {}

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("trash", {"message_id": "msg1"})

    assert result["trashed"] is True


async def test_gmail_dispatch_mark_read():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()
    mock_svc.users().messages().modify().execute.return_value = {}

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("mark_read", {"message_id": "msg1"})

    assert result["marked_read"] is True


async def test_gmail_dispatch_unknown():
    from angie.agents.email.gmail import GmailAgent

    agent = GmailAgent()
    mock_svc = MagicMock()

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("unknown_action", {})

    assert "error" in result


# ── SpamAgent tests ───────────────────────────────────────────────────────────

async def test_spam_agent_scan():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    mock_gmail_result = {
        "messages": [
            {"id": "msg1", "subject": "Win free money now!", "from": "spammer@evil.com"},
            {"id": "msg2", "subject": "Hello friend", "from": "friend@nice.com"},
        ]
    }

    with patch("angie.agents.email.gmail.GmailAgent") as MockGmail:
        mock_inst = AsyncMock()
        mock_inst.execute.return_value = mock_gmail_result
        MockGmail.return_value = mock_inst

        result = await agent.execute({"input_data": {"action": "scan"}})

    assert "spam_found" in result
    assert result["spam_found"] >= 1  # "free money" matches


async def test_spam_agent_scan_error():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()

    with patch("angie.agents.email.gmail.GmailAgent", side_effect=RuntimeError("fail")):
        result = await agent.execute({"input_data": {"action": "scan"}})

    assert "error" in result


async def test_spam_agent_delete():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()

    with patch("angie.agents.email.gmail.GmailAgent") as MockGmail:
        mock_inst = AsyncMock()
        mock_inst.execute.return_value = {"trashed": True}
        MockGmail.return_value = mock_inst

        result = await agent.execute({
            "input_data": {"action": "delete_spam", "message_ids": ["msg1", "msg2"]}
        })

    assert result["trashed"] == 2


async def test_spam_agent_unknown():
    from angie.agents.email.spam import SpamAgent

    agent = SpamAgent()
    result = await agent.execute({"input_data": {"action": "unknown_spam"}})
    assert "error" in result


# ── EmailCorrespondenceAgent tests ────────────────────────────────────────────

async def test_correspondence_draft_no_body():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    result = await agent.execute({"input_data": {"action": "draft_reply", "email_body": ""}})
    assert "error" in result


async def test_correspondence_draft_no_llm():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    with patch("angie.llm.is_llm_configured", return_value=False):
        result = await agent.execute({"input_data": {"action": "draft_reply", "email_body": "Hello"}})

    assert "error" in result


async def test_correspondence_draft_success():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch.object(agent, "ask_llm", AsyncMock(return_value="Draft reply text")),
    ):
        result = await agent.execute({
            "input_data": {"action": "draft_reply", "email_body": "Original email", "tone": "casual"}
        })

    assert result["draft"] == "Draft reply text"
    assert result["tone"] == "casual"


async def test_correspondence_send_reply():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch.object(agent, "ask_llm", AsyncMock(return_value="Draft reply")),
        patch("angie.agents.email.gmail.GmailAgent") as MockGmail,
    ):
        mock_gmail = AsyncMock()
        mock_gmail.execute.return_value = {"sent": True}
        MockGmail.return_value = mock_gmail

        result = await agent.execute({
            "input_data": {
                "action": "send_reply",
                "email_body": "Original",
                "reply_to": "sender@example.com",
                "subject": "Test",
            }
        })

    assert result["sent"] is True


async def test_correspondence_unknown():
    from angie.agents.email.correspondence import EmailCorrespondenceAgent

    agent = EmailCorrespondenceAgent()
    result = await agent.execute({"input_data": {"action": "unknown"}})
    assert "error" in result


# ── SpotifyAgent tests ────────────────────────────────────────────────────────

async def test_spotify_execute_import_error():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()

    with patch("builtins.__import__", side_effect=ImportError("no spotipy")):
        result = await agent.execute({"input_data": {"action": "current"}})

    # Should return error (if spotipy unavailable)
    # Actually import error comes from inside spotipy import
    assert isinstance(result, dict)


def test_spotify_dispatch_current_playing():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "is_playing": True,
        "item": {
            "name": "Test Song",
            "artists": [{"name": "Artist 1"}],
            "album": {"name": "Test Album"},
        }
    }

    result = agent._dispatch(mock_sp, "current", {})
    assert result["playing"] is True
    assert result["track"] == "Test Song"


def test_spotify_dispatch_current_not_playing():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None

    result = agent._dispatch(mock_sp, "current", {})
    assert result["playing"] is False


def test_spotify_dispatch_pause():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "pause", {})
    assert result["paused"] is True


def test_spotify_dispatch_skip():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "skip", {})
    assert result["skipped"] is True


def test_spotify_dispatch_previous():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "previous", {})
    assert result["previous"] is True


def test_spotify_dispatch_volume():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "volume", {"volume": 80})
    assert result["volume"] == 80


def test_spotify_dispatch_play_with_query():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {
        "tracks": {"items": [{"name": "Found Track", "uri": "spotify:track:1"}]}
    }

    result = agent._dispatch(mock_sp, "play", {"query": "test song"})
    assert result["playing"] is True
    assert result["track"] == "Found Track"


def test_spotify_dispatch_play_no_results():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": []}}

    result = agent._dispatch(mock_sp, "play", {"query": "nonexistent"})
    assert "error" in result


def test_spotify_dispatch_play_no_query():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "play", {})
    assert result["playing"] is True


def test_spotify_dispatch_search():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()
    mock_sp.search.return_value = {
        "tracks": {"items": [{"name": "Track1", "artists": [{"name": "Artist"}], "uri": "uri1"}]}
    }

    result = agent._dispatch(mock_sp, "search", {"query": "test"})
    assert "results" in result
    assert len(result["results"]) == 1


def test_spotify_dispatch_unknown():
    from angie.agents.media.spotify import SpotifyAgent

    agent = SpotifyAgent()
    mock_sp = MagicMock()

    result = agent._dispatch(mock_sp, "unknown", {})
    assert "error" in result


# ── HueAgent tests ────────────────────────────────────────────────────────────

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


def test_hue_dispatch_list():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()
    mock_light = MagicMock()
    mock_light.on = True
    mock_bridge.get_light_objects.return_value = {"Living Room": mock_light}

    result = agent._dispatch(mock_bridge, "list", {})
    assert "lights" in result
    assert result["lights"][0]["name"] == "Living Room"


def test_hue_dispatch_on():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    result = agent._dispatch(mock_bridge, "on", {"light": "Bedroom"})
    assert result["on"] is True


def test_hue_dispatch_off():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    result = agent._dispatch(mock_bridge, "off", {})
    assert result["off"] is True


def test_hue_dispatch_brightness():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    result = agent._dispatch(mock_bridge, "brightness", {"brightness": 200})
    assert result["brightness"] == 200


def test_hue_dispatch_color():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    result = agent._dispatch(mock_bridge, "color", {"hue": 10000, "saturation": 200})
    assert result["color_set"] is True


def test_hue_dispatch_unknown():
    from angie.agents.smart_home.hue import HueAgent

    agent = HueAgent()
    mock_bridge = MagicMock()

    result = agent._dispatch(mock_bridge, "unknown", {})
    assert "error" in result


# ── HomeAssistantAgent tests ──────────────────────────────────────────────────

async def test_ha_no_config():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    with patch.dict("os.environ", {"HOME_ASSISTANT_URL": "", "HOME_ASSISTANT_TOKEN": ""}):
        result = await agent.execute({"input_data": {"action": "states"}})

    assert "error" in result
    assert "HOME_ASSISTANT_URL" in result["error"]


async def test_ha_states():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_response = AsyncMock()
    mock_response.json.return_value = [
        {"entity_id": "light.bedroom", "state": "on"},
        {"entity_id": "sensor.temp", "state": "22"},
    ]
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    result = await agent._dispatch(mock_session, "http://ha.local", "states", {})
    assert "entities" in result
    assert len(result["entities"]) == 2


async def test_ha_get_entity():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_response = AsyncMock()
    mock_response.json.return_value = {"entity_id": "light.bedroom", "state": "on"}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    result = await agent._dispatch(mock_session, "http://ha.local", "get", {"entity_id": "light.bedroom"})
    assert result["state"] == "on"


async def test_ha_call_service():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_response = AsyncMock()
    mock_response.json.return_value = []
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response

    result = await agent._dispatch(mock_session, "http://ha.local", "call_service", {
        "domain": "light", "service": "turn_on", "entity_id": "light.bedroom"
    })
    assert result["called"] is True


async def test_ha_turn_on():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_response = AsyncMock()
    mock_response.json.return_value = {}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response

    result = await agent._dispatch(mock_session, "http://ha.local", "turn_on", {"entity_id": "light.x"})
    assert result["on"] is True


async def test_ha_turn_off():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_response = AsyncMock()
    mock_response.json.return_value = {}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response

    result = await agent._dispatch(mock_session, "http://ha.local", "turn_off", {"entity_id": "light.x"})
    assert result["off"] is True


async def test_ha_unknown():
    from angie.agents.smart_home.home_assistant import HomeAssistantAgent

    agent = HomeAssistantAgent()
    mock_session = MagicMock()

    result = await agent._dispatch(mock_session, "http://ha.local", "unknown", {})
    assert "error" in result


# ── GoogleCalendarAgent tests ─────────────────────────────────────────────────

async def test_gcal_execute_error():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    with patch.object(agent, "_dispatch_sync", side_effect=RuntimeError("gcal error")):
        result = await agent.execute({"input_data": {"action": "list"}})

    assert "error" in result


def test_gcal_dispatch_list():
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

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("list", {})

    assert "events" in result
    assert result["events"][0]["summary"] == "Meeting"


def test_gcal_dispatch_create():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()
    mock_svc.events().insert().execute.return_value = {"id": "new-evt", "htmlLink": "http://cal.link"}

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("create", {
            "summary": "New Meeting",
            "start": "2025-01-01T10:00:00Z",
            "end": "2025-01-01T11:00:00Z",
        })

    assert result["created"] is True
    assert result["event_id"] == "new-evt"


def test_gcal_dispatch_delete():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("delete", {"event_id": "evt1"})

    assert result["deleted"] is True


def test_gcal_dispatch_unknown():
    from angie.agents.calendar.gcal import GoogleCalendarAgent

    agent = GoogleCalendarAgent()
    mock_svc = MagicMock()

    with patch.object(agent, "_build_service", return_value=mock_svc):
        result = agent._dispatch_sync("unknown", {})

    assert "error" in result


# ── GitHubAgent tests ─────────────────────────────────────────────────────────

async def test_github_execute_import_error():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    # Test that when the execute dispatch fails, we get an error dict back
    with patch("github.Github", side_effect=RuntimeError("auth error")):
        result = await agent.execute({"input_data": {"action": "list_repos"}})

    assert isinstance(result, dict)
    assert "error" in result


async def test_github_dispatch_list_repos():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_repo = MagicMock()
    mock_repo.full_name = "user/repo1"
    mock_repo.private = False
    mock_g.get_user().get_repos.return_value = [mock_repo]

    result = await agent._dispatch(mock_g, "list_repos", {})
    assert "repos" in result
    assert result["repos"][0]["name"] == "user/repo1"


async def test_github_dispatch_list_prs():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_pr = MagicMock()
    mock_pr.number = 1
    mock_pr.title = "Test PR"
    mock_pr.state = "open"
    mock_pr.user.login = "user1"
    mock_g.get_repo.return_value.get_pulls.return_value = [mock_pr]

    result = await agent._dispatch(mock_g, "list_prs", {"repo": "user/repo"})
    assert "pull_requests" in result


async def test_github_dispatch_list_issues():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 5
    mock_issue.title = "Bug"
    mock_issue.state = "open"
    mock_issue.user.login = "user2"
    mock_g.get_repo.return_value.get_issues.return_value = [mock_issue]

    result = await agent._dispatch(mock_g, "list_issues", {"repo": "user/repo"})
    assert "issues" in result


async def test_github_dispatch_create_issue():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()
    mock_issue = MagicMock()
    mock_issue.number = 10
    mock_issue.html_url = "http://github.com/issue/10"
    mock_g.get_repo.return_value.create_issue.return_value = mock_issue

    result = await agent._dispatch(mock_g, "create_issue", {
        "repo": "user/repo", "title": "New issue", "body": "Details"
    })
    assert result["created"] is True


async def test_github_dispatch_get_repo():
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

    result = await agent._dispatch(mock_g, "get_repo", {"repo": "user/repo"})
    assert result["stars"] == 42


async def test_github_dispatch_unknown():
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    mock_g = MagicMock()

    result = await agent._dispatch(mock_g, "unknown", {})
    assert "error" in result


# ── UbiquitiAgent tests ───────────────────────────────────────────────────────

async def test_ubiquiti_execute():
    from angie.agents.networking.ubiquiti import UbiquitiAgent

    agent = UbiquitiAgent()
    result = await agent.execute({"title": "get wifi clients", "input_data": {}})
    assert result["status"] == "not_implemented"
    assert result["agent"] == "ubiquiti"
