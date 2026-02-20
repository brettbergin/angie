"""Tests for channel adapters — Slack, Discord, Email, iMessage, WebChat."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_settings(**kwargs):
    from angie.config import Settings

    defaults = {"secret_key": "test-secret", "db_password": "testpass"}
    defaults.update(kwargs)
    return Settings(**defaults)


# ── WebChatChannel ─────────────────────────────────────────────────────────────


async def test_web_chat_start():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    await ch.start()  # just logs, no error


async def test_web_chat_stop():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    ch._connections = {"user1": MagicMock(), "user2": MagicMock()}
    await ch.stop()
    assert ch._connections == {}


def test_web_chat_register_unregister():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    ws = MagicMock()
    ch.register_connection("u1", ws)
    assert "u1" in ch._connections
    ch.unregister_connection("u1")
    assert "u1" not in ch._connections


def test_web_chat_unregister_missing():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    ch.unregister_connection("nonexistent")  # should not raise


async def test_web_chat_send_connected():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    mock_ws = AsyncMock()
    ch.register_connection("user1", mock_ws)
    await ch.send("user1", "Hello!")
    mock_ws.send_text.assert_called_once_with("Hello!")


async def test_web_chat_send_not_connected():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    await ch.send("nobody", "Hello!")  # Should not raise


async def test_web_chat_send_failure():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    mock_ws = AsyncMock()
    mock_ws.send_text.side_effect = Exception("connection closed")
    ch.register_connection("user1", mock_ws)
    await ch.send("user1", "Hello!")
    # Should unregister the failed connection
    assert "user1" not in ch._connections


async def test_web_chat_mention_user():
    from angie.channels.web_chat import WebChatChannel

    ch = WebChatChannel()
    mock_ws = AsyncMock()
    ch.register_connection("user1", mock_ws)
    await ch.mention_user("user1", "Hi there!")
    mock_ws.send_text.assert_called_once_with("@user1 Hi there!")


# ── SlackChannel ───────────────────────────────────────────────────────────────


async def test_slack_start():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings(slack_bot_token="xoxb-test")
    mock_client = AsyncMock()
    mock_client.auth_test.return_value = {"user_id": "BTEST123"}

    with (
        patch("angie.channels.slack.get_settings", return_value=mock_settings),
        patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client),
    ):
        ch = SlackChannel()
        await ch.start()

    mock_client.auth_test.assert_called_once()


async def test_slack_start_with_app_token():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings(slack_bot_token="xoxb-test", slack_app_token="xapp-test")
    mock_client = AsyncMock()
    mock_client.auth_test.return_value = {"user_id": "BTEST123"}

    with (
        patch("angie.channels.slack.get_settings", return_value=mock_settings),
        patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client),
    ):
        ch = SlackChannel()
        with patch.object(ch, "_listen", AsyncMock()):
            await ch.start()


async def test_slack_send():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings(slack_bot_token="xoxb-test")
    mock_client = AsyncMock()
    mock_client.chat_postMessage.return_value = {"ok": True}

    with patch("angie.channels.slack.get_settings", return_value=mock_settings):
        ch = SlackChannel()
        ch._client = mock_client
        await ch.send("U123", "Hello Slack!")

    mock_client.chat_postMessage.assert_called_once()


async def test_slack_send_no_client():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings()
    with patch("angie.channels.slack.get_settings", return_value=mock_settings):
        ch = SlackChannel()
        ch._client = None
        await ch.send("U123", "Hello!")  # Should not raise


async def test_slack_mention_user():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings(slack_bot_token="xoxb-test")
    mock_client = AsyncMock()

    with patch("angie.channels.slack.get_settings", return_value=mock_settings):
        ch = SlackChannel()
        ch._client = mock_client
        await ch.mention_user("U123", "Pay attention!")

    mock_client.chat_postMessage.assert_called_once()


async def test_slack_stop():
    from angie.channels.slack import SlackChannel

    mock_settings = _make_settings()
    with patch("angie.channels.slack.get_settings", return_value=mock_settings):
        ch = SlackChannel()
        mock_task = MagicMock()
        ch._listen_task = mock_task
        await ch.stop()

    mock_task.cancel.assert_called_once()


# ── DiscordChannel ─────────────────────────────────────────────────────────────


async def test_discord_start_no_token():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings(discord_bot_token=None)
    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        await ch.start()

    assert ch._bot_task is None


async def test_discord_start_with_token():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings(discord_bot_token="token123")
    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        with patch.object(ch, "_run_bot", AsyncMock()):
            await ch.start()

    assert ch._bot_task is not None
    ch._bot_task.cancel()


async def test_discord_send():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_user = AsyncMock()
    mock_client.fetch_user.return_value = mock_user

    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        ch._client = mock_client
        await ch.send("123456789", "Hello Discord!")

    mock_user.send.assert_called_once_with("Hello Discord!")


async def test_discord_send_no_client():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        ch._client = None
        await ch.send("123", "Hello!")  # Should not raise


async def test_discord_send_with_channel_id():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    mock_client = MagicMock()  # NOT AsyncMock — get_channel is sync
    mock_channel = AsyncMock()
    mock_client.get_channel.return_value = mock_channel

    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        ch._client = mock_client
        await ch.send("123", "Hello!", channel_id="987654321")

    mock_channel.send.assert_called_once_with("Hello!")


async def test_discord_mention_user():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    mock_client = AsyncMock()
    mock_user = AsyncMock()
    mock_client.fetch_user.return_value = mock_user

    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        ch._client = mock_client
        await ch.mention_user("123", "Hey you!")

    mock_user.send.assert_called_once_with("<@123> Hey you!")


async def test_discord_stop():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    mock_client = MagicMock()
    mock_client.is_closed.return_value = False
    mock_client.close = AsyncMock()

    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        ch._client = mock_client
        mock_task = MagicMock()
        ch._bot_task = mock_task
        await ch.stop()

    mock_client.close.assert_called_once()
    mock_task.cancel.assert_called_once()


async def test_discord_dispatch_event():
    from angie.channels.discord import DiscordChannel

    mock_settings = _make_settings()
    with patch("angie.channels.discord.get_settings", return_value=mock_settings):
        ch = DiscordChannel()
        with patch("angie.core.events.router.dispatch", AsyncMock()) as mock_dispatch:
            await ch._dispatch_event("user1", "Hello", "channel1")

    mock_dispatch.assert_called_once()


# ── EmailChannel ───────────────────────────────────────────────────────────────


async def test_email_start_no_imap():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings(
        email_smtp_host="smtp.gmail.com",
        email_imap_host=None,
        email_username="test@gmail.com",
    )
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        await ch.start()

    assert ch._poll_task is None


async def test_email_start_with_imap():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings(
        email_smtp_host="smtp.gmail.com",
        email_imap_host="imap.gmail.com",
        email_username="test@gmail.com",
        email_password="pass",
    )
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        with patch.object(ch, "_poll_inbox", AsyncMock()):
            await ch.start()

    assert ch._poll_task is not None
    ch._poll_task.cancel()


async def test_email_stop():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings()
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        mock_task = MagicMock()
        ch._poll_task = mock_task
        await ch.stop()

    mock_task.cancel.assert_called_once()


async def test_email_send():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings(
        email_smtp_host="smtp.gmail.com",
        email_username="test@gmail.com",
        email_password="pass",
    )
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        with patch.object(ch, "_smtp_send") as mock_smtp:
            await ch.send("recipient@example.com", "Hello email!")

    mock_smtp.assert_called_once()


async def test_email_send_no_config():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings(email_smtp_host=None)
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        await ch.send("test@example.com", "Hello!")  # Should log warning but not raise


async def test_email_mention_user():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings(
        email_smtp_host="smtp.gmail.com",
        email_username="test@gmail.com",
        email_password="pass",
    )
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        with patch.object(ch, "_smtp_send") as mock_smtp:
            await ch.mention_user("user@example.com", "Attention needed!")

    mock_smtp.assert_called_once()


def test_email_extract_body_plain():
    import email as email_lib

    from angie.channels.email import EmailChannel

    mock_settings = _make_settings()
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        msg = email_lib.message_from_string("Subject: Test\n\nHello body!")
        result = ch._extract_body(msg)
    assert "Hello body" in result


async def test_email_dispatch_event():
    from angie.channels.email import EmailChannel

    mock_settings = _make_settings()
    with patch("angie.channels.email.get_settings", return_value=mock_settings):
        ch = EmailChannel()
        with patch("angie.core.events.router.dispatch", AsyncMock()) as mock_dispatch:
            await ch._dispatch_event("sender@test.com", "Subject", "Body text")

    mock_dispatch.assert_called_once()


# ── IMessageChannel ────────────────────────────────────────────────────────────


async def test_imessage_start():
    from angie.channels.imessage import IMessageChannel

    mock_settings = _make_settings(
        bluebubbles_url="http://bb.local",
        bluebubbles_password="password",
    )
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_http.get.return_value = mock_resp

    with (
        patch("angie.channels.imessage.get_settings", return_value=mock_settings),
        patch("httpx.AsyncClient", return_value=mock_http),
    ):
        ch = IMessageChannel()
        with patch.object(ch, "_poll_messages", AsyncMock()):
            await ch.start()

    assert ch._poll_task is not None
    ch._poll_task.cancel()


async def test_imessage_stop():
    from angie.channels.imessage import IMessageChannel

    mock_settings = _make_settings()
    mock_http = AsyncMock()
    with patch("angie.channels.imessage.get_settings", return_value=mock_settings):
        ch = IMessageChannel()
        ch._http = mock_http
        mock_task = MagicMock()
        ch._poll_task = mock_task
        await ch.stop()

    mock_task.cancel.assert_called_once()
    mock_http.aclose.assert_called_once()


async def test_imessage_send():
    from angie.channels.imessage import IMessageChannel

    mock_settings = _make_settings(
        bluebubbles_url="http://bb.local",
        bluebubbles_password="pass",
    )
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_http.post.return_value = mock_resp

    with patch("angie.channels.imessage.get_settings", return_value=mock_settings):
        ch = IMessageChannel()
        ch._http = mock_http
        await ch.send("+15551234567", "Hello iMessage!")

    mock_http.post.assert_called_once()


async def test_imessage_send_no_client():
    from angie.channels.imessage import IMessageChannel

    mock_settings = _make_settings()
    with patch("angie.channels.imessage.get_settings", return_value=mock_settings):
        ch = IMessageChannel()
        ch._http = None
        await ch.send("+15551234567", "Hello!")  # Should not raise


async def test_imessage_mention_user():
    from angie.channels.imessage import IMessageChannel

    mock_settings = _make_settings(
        bluebubbles_url="http://bb.local",
        bluebubbles_password="pass",
    )
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_http.post.return_value = mock_resp

    with patch("angie.channels.imessage.get_settings", return_value=mock_settings):
        ch = IMessageChannel()
        ch._http = mock_http
        await ch.mention_user("+15551234567", "Urgent!")

    mock_http.post.assert_called_once()
