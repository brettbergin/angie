"""Tests for internal channel functionality."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_settings(**kw):
    s = MagicMock()
    s.slack_bot_token = kw.get("slack_bot_token", "xoxb-test")
    s.slack_app_token = kw.get("slack_app_token", "xapp-test")
    s.discord_bot_token = kw.get("discord_bot_token", "discord-test")
    s.imessage_bluebubbles_url = kw.get("imessage_bluebubbles_url", "http://bb.local:1234")
    s.imessage_bluebubbles_password = kw.get("imessage_bluebubbles_password", "secret")
    s.email_imap_server = kw.get("email_imap_server", "imap.example.com")
    s.email_address = kw.get("email_address", "test@example.com")
    s.email_password = kw.get("email_password", "pass")
    s.email_smtp_server = kw.get("email_smtp_server", "smtp.example.com")
    s.email_smtp_port = kw.get("email_smtp_port", 587)
    return s


# ── channels/base.py: ChannelManager builder ─────────────────────────────────


def test_channel_manager_build_with_slack_discord():
    """_build_manager detects enabled services by settings attributes."""
    mock_settings = _make_settings()
    mock_settings.slack_bot_token = "xoxb-xxx"
    mock_settings.discord_bot_token = "discord-xxx"

    with patch("angie.config.get_settings", return_value=mock_settings):
        with (
            patch("angie.channels.slack.SlackChannel") as mock_slack_cls,
            patch("angie.channels.discord.DiscordChannel") as mock_discord_cls,
        ):
            mock_slack_cls.return_value = MagicMock(channel_type="slack")
            mock_discord_cls.return_value = MagicMock(channel_type="discord")

            from angie.channels import base as _base_mod

            # Reset the global manager so _build_manager is called fresh
            _base_mod._manager = None
            mgr = _base_mod.get_channel_manager()
            _base_mod._manager = None  # reset for other tests

    assert isinstance(mgr._channels, dict)


@pytest.mark.asyncio
async def test_channel_manager_send_dispatches():
    from angie.channels.base import ChannelManager

    manager = ChannelManager()

    mock_channel = AsyncMock()
    manager._channels = {"slack": mock_channel}

    await manager.send("U123", "hello", channel_type="slack")
    mock_channel.send.assert_called_once_with("U123", "hello")


@pytest.mark.asyncio
async def test_channel_manager_send_unknown_channel():
    from angie.channels.base import ChannelManager

    manager = ChannelManager()
    manager._channels = {}

    # Should not raise
    await manager.send("U123", "hello", channel_type="slack")


# ── channels/slack.py: _dispatch_event ────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_dispatch_event():
    """Cover _dispatch_event converting a message to an AngieEvent."""
    slack_sdk_modules = {
        "slack_sdk": MagicMock(),
        "slack_sdk.web.async_client": MagicMock(),
        "slack_sdk.socket_mode.aiohttp": MagicMock(),
        "slack_sdk.socket_mode.request": MagicMock(),
        "slack_sdk.socket_mode.response": MagicMock(),
    }
    sys.modules.pop("angie.channels.slack", None)
    with patch.dict("sys.modules", slack_sdk_modules):
        from angie.channels import slack as _slack_mod

        ch = _slack_mod.SlackChannel.__new__(_slack_mod.SlackChannel)
        ch.settings = _make_settings()
        ch._client = None
        ch._socket_handler = None
        ch._listen_task = None

        mock_router = MagicMock()
        mock_router.dispatch = AsyncMock()

        with patch("angie.core.events.router", mock_router):
            await ch._dispatch_event(user_id="U123", text="hello world", channel="C456")

    mock_router.dispatch.assert_called_once()


# ── channels/discord.py: _dispatch_event ─────────────────────────────────────


@pytest.mark.asyncio
async def test_discord_dispatch_event():
    """Cover _dispatch_event in DiscordChannel."""
    mock_discord = MagicMock()
    mock_discord.Intents.default.return_value = MagicMock()
    mock_discord.Client = MagicMock()

    sys.modules.pop("angie.channels.discord", None)
    with patch.dict("sys.modules", {"discord": mock_discord}):
        from angie.channels import discord as _discord_mod

        ch = _discord_mod.DiscordChannel.__new__(_discord_mod.DiscordChannel)
        ch.settings = _make_settings()
        ch._client = None
        ch._bot_task = None

        mock_router = MagicMock()
        mock_router.dispatch = AsyncMock()

        with patch("angie.core.events.router", mock_router):
            await ch._dispatch_event(user_id="U789", text="hello discord", channel_id="C111")

    mock_router.dispatch.assert_called_once()


# ── channels/email.py: _check_inbox + _poll_inbox ────────────────────────────


@pytest.mark.asyncio
async def test_email_dispatch_event():
    """Cover email _dispatch_event."""
    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = _make_settings()
    ch._poll_task = None

    mock_router = MagicMock()
    mock_router.dispatch = AsyncMock()

    with patch("angie.core.events.router", mock_router):
        await ch._dispatch_event("sender@example.com", "Test Subject", "Hello there")

    mock_router.dispatch.assert_called_once()


def test_email_check_inbox_with_imaplib_error():
    """_check_inbox catches IMAP errors gracefully."""
    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = _make_settings()
    ch._poll_task = None

    with patch("imaplib.IMAP4_SSL", side_effect=OSError("connection refused")):
        ch._check_inbox()  # Should not raise


def test_email_extract_body_multipart():
    """_extract_body on a multipart message returns text/plain part."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)

    msg = MIMEMultipart()
    msg.attach(MIMEText("Plain text body", "plain"))
    msg.attach(MIMEText("<b>HTML body</b>", "html"))

    body = ch._extract_body(msg)
    assert "Plain text body" in body


def test_email_extract_body_simple():
    """_extract_body on simple text/plain returns the payload."""
    from email.mime.text import MIMEText

    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)

    msg = MIMEText("Simple plain body", "plain")
    body = ch._extract_body(msg)
    assert "Simple plain body" in body


# ── channels/imessage.py: _poll_messages + old-message skip ──────────────────


@pytest.mark.asyncio
async def test_imessage_dispatch_event():
    """Cover iMessage _dispatch_event."""

    from angie.channels.imessage import IMessageChannel

    ch = IMessageChannel.__new__(IMessageChannel)
    ch.settings = _make_settings()
    ch._http = None
    ch._last_ms = 0
    ch._poll_task = None

    mock_router = MagicMock()
    mock_router.dispatch = AsyncMock()

    with patch("angie.core.events.router", mock_router):
        await ch._dispatch_event("+15551234567", "Hello from iMessage")

    mock_router.dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_imessage_check_new_messages_no_http():
    """_check_new_messages returns immediately when _http is None."""
    from angie.channels.imessage import IMessageChannel

    ch = IMessageChannel.__new__(IMessageChannel)
    ch.settings = _make_settings()
    ch._http = None
    ch._last_ms = 0
    ch._poll_task = None

    await ch._check_new_messages()
    # No error = pass


@pytest.mark.asyncio
async def test_imessage_check_new_messages_skips_old():
    """Messages with dateCreated <= _last_ms are skipped."""

    from angie.channels.imessage import IMessageChannel

    ch = IMessageChannel.__new__(IMessageChannel)
    ch.settings = _make_settings()
    ch._last_ms = 9999
    ch._poll_task = None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"dateCreated": 1000, "text": "old message", "handle": {"address": "+1555"}}]
    }

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    ch._http = mock_http

    mock_router = MagicMock()
    mock_router.dispatch = AsyncMock()

    with patch("angie.core.events.router", mock_router):
        await ch._check_new_messages()

    mock_router.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_imessage_check_new_messages_processes_new():
    """New messages (dateCreated > _last_ms) are dispatched."""
    from angie.channels.imessage import IMessageChannel

    ch = IMessageChannel.__new__(IMessageChannel)
    ch.settings = _make_settings()
    ch._last_ms = 1000
    ch._poll_task = None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"dateCreated": 2000, "text": "new message", "handle": {"address": "+1555"}}]
    }

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)
    ch._http = mock_http

    mock_router = MagicMock()
    mock_router.dispatch = AsyncMock()

    with patch("angie.core.events.router", mock_router):
        await ch._check_new_messages()

    mock_router.dispatch.assert_called_once()
    assert ch._last_ms == 2000


# ── iMessage _poll_messages exception path ─────────────────────────────────────


@pytest.mark.asyncio
async def test_imessage_poll_messages_exception():
    """Cover _poll_messages exception path (lines 55-56)."""
    import asyncio as _asyncio

    from angie.channels.imessage import IMessageChannel

    ch = IMessageChannel.__new__(IMessageChannel)
    ch.settings = MagicMock()
    ch.settings.bluebubbles_url = "http://bb.local:1234"
    ch.settings.bluebubbles_password = "secret"
    ch._http = None
    ch._last_ts = 0

    sleep_calls = []

    async def fake_sleep(n):
        sleep_calls.append(n)
        if len(sleep_calls) >= 1:
            raise _asyncio.CancelledError()

    with (
        patch("angie.channels.imessage.asyncio.sleep", side_effect=fake_sleep),
        patch.object(
            ch,
            "_check_new_messages",
            new_callable=AsyncMock,
            side_effect=RuntimeError("poll error"),
        ),
    ):
        try:
            await ch._poll_messages()
        except _asyncio.CancelledError:
            pass


# ── Email _poll_inbox and _check_inbox ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_email_poll_inbox():
    """Cover _poll_inbox lines 40-45: exception path + sleep."""
    import asyncio as _asyncio

    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = MagicMock()

    sleep_calls = []

    async def fake_sleep(n):
        sleep_calls.append(n)
        raise _asyncio.CancelledError()

    async def fake_run_in_executor(executor, fn):
        raise RuntimeError("imap fail")

    with (
        patch("angie.channels.email.asyncio.sleep", side_effect=fake_sleep),
        patch("asyncio.get_event_loop") as mock_loop,
    ):
        mock_loop_obj = MagicMock()
        mock_loop_obj.run_in_executor = AsyncMock(side_effect=RuntimeError("fail"))
        mock_loop.return_value = mock_loop_obj

        try:
            await ch._poll_inbox()
        except _asyncio.CancelledError:
            pass


def test_email_check_inbox_imaplib():
    """Cover _check_inbox using mocked imaplib (lines 47-73)."""
    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = MagicMock()
    ch.settings.email_imap_host = "imap.example.com"
    ch.settings.email_imap_port = 993
    ch.settings.email_username = "test@example.com"
    ch.settings.email_password = "pass"

    # Build a simple raw email
    raw_msg = b"From: sender@example.com\r\nSubject: Test\r\n\r\nHello world"

    mock_conn = MagicMock()
    mock_conn.login.return_value = ("OK", [b"Logged in"])
    mock_conn.select.return_value = ("OK", [b"1"])
    mock_conn.search.return_value = ("OK", [b"1"])
    mock_conn.fetch.return_value = ("OK", [(b"1", raw_msg)])

    mock_loop = MagicMock()
    mock_future = MagicMock()
    mock_loop.run_coroutine_threadsafe = MagicMock(return_value=mock_future)

    with (
        patch("angie.channels.email.imaplib.IMAP4_SSL", return_value=mock_conn),
        patch("asyncio.get_event_loop", return_value=mock_loop),
        patch.object(ch, "_dispatch_event", new_callable=AsyncMock),
    ):
        ch._check_inbox()

    mock_conn.login.assert_called_once()
    mock_conn.logout.assert_called_once()


def test_email_check_inbox_exception():
    """Cover the IMAP error exception path (lines 72-73)."""
    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = MagicMock()
    ch.settings.email_imap_host = "imap.example.com"
    ch.settings.email_imap_port = 993
    ch.settings.email_username = "test@example.com"
    ch.settings.email_password = "pass"

    with patch("angie.channels.email.imaplib.IMAP4_SSL", side_effect=OSError("connection refused")):
        # Should not raise — exception is caught and logged
        ch._check_inbox()


# ── Slack _listen method ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_listen():
    """Cover _listen() by mocking SocketModeClient and cancelling the loop."""
    import asyncio as _asyncio

    from angie.channels.slack import SlackChannel

    ch = SlackChannel.__new__(SlackChannel)
    ch.settings = MagicMock()
    ch.settings.slack_app_token = "xapp-test"
    ch.settings.slack_bot_token = "xoxb-test"
    ch._client = AsyncMock()
    ch._client.auth_test = AsyncMock(return_value={"user_id": "U123"})

    sleep_call_count = 0

    async def fake_sleep(n):
        nonlocal sleep_call_count
        sleep_call_count += 1
        raise _asyncio.CancelledError()

    mock_sm_client = MagicMock()
    mock_sm_client.socket_mode_request_listeners = []
    mock_sm_client.connect = AsyncMock()

    mock_sm_cls = MagicMock(return_value=mock_sm_client)
    mock_request_cls = MagicMock()
    mock_response_cls = MagicMock()

    with (
        patch.dict(
            "sys.modules",
            {
                "slack_sdk.socket_mode.aiohttp": MagicMock(SocketModeClient=mock_sm_cls),
                "slack_sdk.socket_mode.request": MagicMock(SocketModeRequest=mock_request_cls),
                "slack_sdk.socket_mode.response": MagicMock(SocketModeResponse=mock_response_cls),
            },
        ),
        patch("angie.channels.slack.asyncio.sleep", side_effect=fake_sleep),
        patch("angie.core.events.router"),
    ):
        try:
            await ch._listen()
        except _asyncio.CancelledError:
            pass

    mock_sm_client.connect.assert_called_once()


# ── Discord _run_bot method ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discord_run_bot():
    """Cover _run_bot() by mocking discord module and cancelling the bot."""
    import asyncio as _asyncio

    from angie.channels.discord import DiscordChannel

    ch = DiscordChannel.__new__(DiscordChannel)
    ch.settings = MagicMock()
    ch.settings.discord_bot_token = "test-token"
    ch._client = None

    mock_client = MagicMock()
    mock_client.user = MagicMock()
    mock_client.user.id = "B123"
    mock_client.start = AsyncMock(side_effect=_asyncio.CancelledError())
    mock_client.close = AsyncMock()
    mock_client.event = lambda fn: fn  # passthrough decorator

    mock_intents = MagicMock()
    mock_discord = MagicMock()
    mock_discord.Intents.default.return_value = mock_intents
    mock_discord.Client.return_value = mock_client
    mock_discord.DMChannel = type("DMChannel", (), {})

    with patch.dict("sys.modules", {"discord": mock_discord}), patch("angie.core.events.router"):
        try:
            await ch._run_bot()
        except Exception:
            pass

    mock_client.close.assert_called_once()


# ── Slack _process inner callback ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_listen_process_callback():
    """Cover the _process callback inside _listen (lines 44-67)."""
    import asyncio as _asyncio

    from angie.channels.slack import SlackChannel

    ch = SlackChannel.__new__(SlackChannel)
    ch.settings = MagicMock()
    ch.settings.slack_app_token = "xapp-test"
    ch.settings.slack_bot_token = "xoxb-test"
    ch._client = AsyncMock()
    ch._client.auth_test = AsyncMock(return_value={"user_id": "U123"})
    ch._dispatch_event = AsyncMock()

    sleep_calls = []

    async def fake_sleep(n):
        sleep_calls.append(n)
        raise _asyncio.CancelledError()

    mock_sm_client = MagicMock()
    mock_sm_client.socket_mode_request_listeners = []
    mock_sm_client.connect = AsyncMock()

    mock_response_cls = MagicMock(return_value=MagicMock())

    with (
        patch.dict(
            "sys.modules",
            {
                "slack_sdk.socket_mode.aiohttp": MagicMock(
                    SocketModeClient=MagicMock(return_value=mock_sm_client)
                ),
                "slack_sdk.socket_mode.request": MagicMock(SocketModeRequest=MagicMock()),
                "slack_sdk.socket_mode.response": MagicMock(SocketModeResponse=mock_response_cls),
            },
        ),
        patch("angie.channels.slack.asyncio.sleep", side_effect=fake_sleep),
    ):
        try:
            await ch._listen()
        except _asyncio.CancelledError:
            pass

    # Retrieve and invoke the _process callback
    assert len(mock_sm_client.socket_mode_request_listeners) == 1
    _process = mock_sm_client.socket_mode_request_listeners[0]

    # Case 1: non-events_api type → early return
    req1 = MagicMock()
    req1.type = "interactive"
    req1.envelope_id = "env1"
    req1.payload = {}
    mock_sm_client.send_socket_mode_response = AsyncMock()
    await _process(mock_sm_client, req1)

    # Case 2: events_api but wrong event type
    req2 = MagicMock()
    req2.type = "events_api"
    req2.envelope_id = "env2"
    req2.payload = {"event": {"type": "reaction_added"}}
    await _process(mock_sm_client, req2)

    # Case 3: message with subtype → skip
    req3 = MagicMock()
    req3.type = "events_api"
    req3.envelope_id = "env3"
    req3.payload = {"event": {"type": "message", "subtype": "bot_message"}}
    await _process(mock_sm_client, req3)

    # Case 4: message in DM (channel starts with D) → dispatch
    req4 = MagicMock()
    req4.type = "events_api"
    req4.envelope_id = "env4"
    req4.payload = {
        "event": {"type": "message", "text": "hello", "user": "U999", "channel": "D001"}
    }
    await _process(mock_sm_client, req4)
    ch._dispatch_event.assert_called_once()

    # Case 5: message with mention → dispatch
    ch._dispatch_event.reset_mock()
    req5 = MagicMock()
    req5.type = "events_api"
    req5.envelope_id = "env5"
    req5.payload = {
        "event": {"type": "message", "text": "<@U123> hey", "user": "U888", "channel": "C001"}
    }
    await _process(mock_sm_client, req5)
    ch._dispatch_event.assert_called_once()

    # Case 6: message not in DM and not mentioning bot → no dispatch
    ch._dispatch_event.reset_mock()
    req6 = MagicMock()
    req6.type = "events_api"
    req6.envelope_id = "env6"
    req6.payload = {
        "event": {"type": "message", "text": "random", "user": "U888", "channel": "C001"}
    }
    await _process(mock_sm_client, req6)
    ch._dispatch_event.assert_not_called()


# ── Discord on_ready and on_message callbacks ───────────────────────────────────


@pytest.mark.asyncio
async def test_discord_run_bot_callbacks():
    """Cover on_ready and on_message callbacks inside _run_bot."""
    import asyncio as _asyncio

    from angie.channels.discord import DiscordChannel

    ch = DiscordChannel.__new__(DiscordChannel)
    ch.settings = MagicMock()
    ch.settings.discord_bot_token = "test-token"
    ch._client = None
    ch._dispatch_event = AsyncMock()

    registered_events: dict = {}

    mock_discord_user = MagicMock()
    mock_discord_user.id = "B123"

    mock_client = MagicMock()
    mock_client.user = mock_discord_user
    mock_client.close = AsyncMock()

    def capture_event(fn):
        registered_events[fn.__name__] = fn
        return fn

    mock_client.event = capture_event

    # First call: start raises CancelledError after registering events
    async def fake_start(token):
        raise _asyncio.CancelledError()

    mock_client.start = fake_start

    mock_dm_channel_cls = type("DMChannel", (), {})
    mock_discord = MagicMock()
    mock_discord.Intents.default.return_value = MagicMock()
    mock_discord.Client.return_value = mock_client
    mock_discord.DMChannel = mock_dm_channel_cls

    with patch.dict("sys.modules", {"discord": mock_discord}):
        try:
            await ch._run_bot()
        except Exception:
            pass

    # Test on_ready
    on_ready = registered_events.get("on_ready")
    assert on_ready is not None
    await on_ready()

    # Test on_message — author is bot → return early
    on_message = registered_events.get("on_message")
    assert on_message is not None
    msg_self = MagicMock()
    msg_self.author = mock_discord_user
    await on_message(msg_self)

    # Test on_message — DM from another user
    ch._dispatch_event.reset_mock()
    msg_dm = MagicMock()
    msg_dm.author = MagicMock()
    msg_dm.author.id = "U001"
    msg_dm.content = "hello"
    msg_dm.channel = mock_dm_channel_cls()
    msg_dm.channel.id = "D001"
    msg_dm.mentions = []
    await on_message(msg_dm)
    ch._dispatch_event.assert_called_once()

    # Test on_message — mention in non-DM
    ch._dispatch_event.reset_mock()
    msg_mention = MagicMock()
    msg_mention.author = MagicMock()
    msg_mention.author.id = "U002"
    msg_mention.content = f"<@{mock_discord_user.id}> help"
    msg_mention.channel = MagicMock()
    msg_mention.channel.id = "C001"
    msg_mention.channel.__class__ = type("TextChannel", (), {})
    msg_mention.mentions = [mock_discord_user]
    await on_message(msg_mention)
    ch._dispatch_event.assert_called_once()

    # Test on_message — not DM, not mentioned → no dispatch
    ch._dispatch_event.reset_mock()
    msg_other = MagicMock()
    msg_other.author = MagicMock()
    msg_other.author.id = "U003"
    msg_other.content = "general chat"
    msg_other.channel = MagicMock()
    msg_other.channel.__class__ = type("TextChannel", (), {})
    msg_other.mentions = []
    await on_message(msg_other)
    ch._dispatch_event.assert_not_called()


def test_email_check_inbox_null_raw():
    """Cover the 'if not raw: continue' branch (line 58) in _check_inbox."""
    from angie.channels.email import EmailChannel

    ch = EmailChannel.__new__(EmailChannel)
    ch.settings = MagicMock()
    ch.settings.email_imap_host = "imap.example.com"
    ch.settings.email_imap_port = 993
    ch.settings.email_username = "test@example.com"
    ch.settings.email_password = "pass"

    mock_conn = MagicMock()
    mock_conn.login.return_value = ("OK", [b"Logged in"])
    mock_conn.select.return_value = ("OK", [b"1"])
    mock_conn.search.return_value = ("OK", [b"1"])
    # Return fetch result where raw is None
    mock_conn.fetch.return_value = ("OK", [(b"1", None)])

    with patch("angie.channels.email.imaplib.IMAP4_SSL", return_value=mock_conn):
        ch._check_inbox()

    # Should complete without dispatching any events
    mock_conn.logout.assert_called_once()
