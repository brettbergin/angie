"""Tests for Discord, Email, and iMessage channel adapters."""

from __future__ import annotations

import asyncio
import os
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_settings(**kwargs):
    from angie.config import Settings
    defaults = dict(secret_key="k", db_password="pass")
    defaults.update(kwargs)
    return Settings(**defaults)  # type: ignore[call-arg]


# ──────────────────────────────────────────────────────────────────────────────
# DiscordChannel
# ──────────────────────────────────────────────────────────────────────────────

class TestDiscordChannel:
    def _make_channel(self, **kwargs):
        s = _make_settings(**kwargs)
        with patch("angie.config.get_settings", return_value=s):
            from angie.channels.discord import DiscordChannel
            return DiscordChannel()

    @pytest.mark.asyncio
    async def test_start_no_token_skips(self):
        ch = self._make_channel(discord_bot_token=None)
        await ch.start()
        assert ch._bot_task is None

    @pytest.mark.asyncio
    async def test_start_with_token_creates_task(self):
        ch = self._make_channel()
        # Directly override settings to simulate configured token
        ch.settings = _make_settings(discord_bot_token="fake-token")
        with patch.object(ch, "_run_bot", new_callable=AsyncMock):
            with patch.object(asyncio, "create_task", return_value=MagicMock()) as mock_ct:
                await ch.start()
                mock_ct.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_no_client(self):
        ch = self._make_channel()
        ch._client = None
        ch._bot_task = None
        await ch.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_stop_with_client(self):
        ch = self._make_channel()
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        mock_client.close = AsyncMock()
        ch._client = mock_client
        mock_task = MagicMock()
        ch._bot_task = mock_task
        await ch.stop()
        mock_client.close.assert_called_once()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_client_already_closed(self):
        ch = self._make_channel()
        mock_client = MagicMock()
        mock_client.is_closed.return_value = True
        mock_client.close = AsyncMock()
        ch._client = mock_client
        await ch.stop()
        mock_client.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_no_client(self):
        ch = self._make_channel()
        ch._client = None
        await ch.send("123", "hello")  # should not raise

    @pytest.mark.asyncio
    async def test_send_to_channel(self):
        ch = self._make_channel()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client = MagicMock()
        mock_client.get_channel.return_value = mock_channel
        ch._client = mock_client
        await ch.send("123", "hello", channel_id="456")
        mock_channel.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_to_channel_not_found_dm_fallback(self):
        ch = self._make_channel()
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_client = MagicMock()
        mock_client.get_channel.return_value = None
        mock_client.fetch_user = AsyncMock(return_value=mock_user)
        ch._client = mock_client
        await ch.send("123", "hello", channel_id="456")
        mock_user.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_dm(self):
        ch = self._make_channel()
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_client = MagicMock()
        mock_client.fetch_user = AsyncMock(return_value=mock_user)
        ch._client = mock_client
        await ch.send("123", "hello")
        mock_user.send.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_dm_failure_logs_warning(self):
        ch = self._make_channel()
        mock_client = MagicMock()
        mock_client.fetch_user = AsyncMock(side_effect=Exception("rate limited"))
        ch._client = mock_client
        await ch.send("123", "hello")  # should not raise

    @pytest.mark.asyncio
    async def test_mention_user(self):
        ch = self._make_channel()
        ch.send = AsyncMock()
        await ch.mention_user("456", "hi there")
        ch.send.assert_called_once_with("456", "<@456> hi there")

    @pytest.mark.asyncio
    async def test_dispatch_event(self):
        ch = self._make_channel()
        with patch("angie.core.events.router") as mock_router:
            mock_router.dispatch = AsyncMock()
            await ch._dispatch_event("user1", "hello", "chan1")
        mock_router.dispatch.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# EmailChannel
# ──────────────────────────────────────────────────────────────────────────────

class TestEmailChannel:
    def _make_channel(self, **kwargs):
        s = _make_settings(**kwargs)
        with patch("angie.config.get_settings", return_value=s):
            from angie.channels.email import EmailChannel
            return EmailChannel()

    @pytest.mark.asyncio
    async def test_start_no_imap(self):
        ch = self._make_channel()
        await ch.start()
        assert ch._poll_task is None

    @pytest.mark.asyncio
    async def test_start_with_imap_creates_task(self):
        ch = self._make_channel()
        ch.settings = _make_settings(
            email_imap_host="imap.gmail.com",
            email_username="test@example.com",
            email_password="apppass",
        )
        with patch.object(asyncio, "create_task", return_value=MagicMock()):
            with patch.object(ch, "_poll_inbox", new_callable=AsyncMock):
                await ch.start()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        ch = self._make_channel()
        mock_task = MagicMock()
        ch._poll_task = mock_task
        await ch.stop()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_no_config(self):
        ch = self._make_channel()
        await ch.send("user@example.com", "hello")  # should not raise

    @pytest.mark.asyncio
    async def test_send_with_smtp(self):
        ch = self._make_channel()
        ch.settings = _make_settings(
            email_smtp_host="smtp.gmail.com",
            email_smtp_port=587,
            email_username="test@example.com",
            email_password="apppass",
        )

        with patch.object(ch, "_smtp_send") as mock_send:
            await ch.send("to@example.com", "body text", subject="Test Subject")
        mock_send.assert_called_once()
        msg_arg = mock_send.call_args[0][0]
        assert msg_arg["Subject"] == "Test Subject"

    def test_smtp_send(self):
        ch = self._make_channel()
        ch.settings = _make_settings(
            email_smtp_host="smtp.example.com",
            email_smtp_port=587,
            email_username="from@example.com",
            email_password="secret",
        )

        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        with patch("smtplib.SMTP", return_value=mock_server):
            msg = MIMEText("hello")
            msg["Subject"] = "Test"
            msg["From"] = "from@example.com"
            msg["To"] = "to@example.com"
            ch._smtp_send(msg, "to@example.com")
        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()

    def test_extract_body_plain(self):
        import email as email_lib
        ch = self._make_channel()
        raw = b"From: a@b.com\r\nContent-Type: text/plain\r\n\r\nhello world"
        msg = email_lib.message_from_bytes(raw)
        body = ch._extract_body(msg)
        assert "hello world" in body

    def test_extract_body_multipart(self):
        import email as email_lib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText as _MIMEText

        ch = self._make_channel()
        outer = MIMEMultipart("alternative")
        outer.attach(_MIMEText("plain text", "plain"))
        outer.attach(_MIMEText("<b>html</b>", "html"))
        raw = outer.as_bytes()
        msg = email_lib.message_from_bytes(raw)
        body = ch._extract_body(msg)
        assert "plain text" in body

    @pytest.mark.asyncio
    async def test_dispatch_event(self):
        ch = self._make_channel()
        with patch("angie.core.events.router") as mock_router:
            mock_router.dispatch = AsyncMock()
            await ch._dispatch_event("sender@example.com", "Subject Line", "Body content")
        mock_router.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_mention_user(self):
        ch = self._make_channel()
        ch.send = AsyncMock()
        await ch.mention_user("user@example.com", "hello")
        ch.send.assert_called_once()
        kwargs = ch.send.call_args[1]
        assert kwargs.get("subject") == "Angie needs your attention"


# ──────────────────────────────────────────────────────────────────────────────
# IMessageChannel
# ──────────────────────────────────────────────────────────────────────────────

class TestIMessageChannel:
    def _make_channel(self, **kwargs):
        s = _make_settings(**kwargs)
        with patch("angie.config.get_settings", return_value=s):
            from angie.channels.imessage import IMessageChannel
            return IMessageChannel()

    def test_base_url_property(self):
        ch = self._make_channel()
        ch.settings = _make_settings(bluebubbles_url="http://bb.local:1234")
        assert ch._base_url == "http://bb.local:1234/api/v1"

    def test_auth_property(self):
        ch = self._make_channel()
        ch.settings = _make_settings(bluebubbles_password="secret123")
        assert ch._auth == {"password": "secret123"}

    def test_auth_property_no_password(self):
        ch = self._make_channel()
        assert ch._auth == {"password": ""}

    @pytest.mark.asyncio
    async def test_stop_cancels_task_and_closes_http(self):
        ch = self._make_channel()
        mock_task = MagicMock()
        mock_http = AsyncMock()
        ch._poll_task = mock_task
        ch._http = mock_http
        await ch.stop()
        mock_task.cancel.assert_called_once()
        mock_http.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_no_task_no_http(self):
        ch = self._make_channel()
        await ch.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_send_no_http_client(self):
        ch = self._make_channel()
        ch._http = None
        await ch.send("+15555550100", "hello")  # should not raise

    @pytest.mark.asyncio
    async def test_send_posts_message(self):
        ch = self._make_channel()
        ch.settings = _make_settings(bluebubbles_password="pass")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        ch._http = mock_http
        await ch.send("+15555550100", "hello world")
        mock_http.post.assert_called_once()
        call_kwargs = mock_http.post.call_args
        assert "hello world" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_mention_user(self):
        ch = self._make_channel()
        ch.send = AsyncMock()
        await ch.mention_user("+15555550100", "check this out")
        ch.send.assert_called_once()
        args = ch.send.call_args[0]
        assert "check this out" in args[1]

    @pytest.mark.asyncio
    async def test_dispatch_event(self):
        ch = self._make_channel()
        with patch("angie.core.events.router") as mock_router:
            mock_router.dispatch = AsyncMock()
            await ch._dispatch_event("+15555550100", "test message")
        mock_router.dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_new_messages_no_http(self):
        ch = self._make_channel()
        ch._http = None
        await ch._check_new_messages()  # should not raise

    @pytest.mark.asyncio
    async def test_check_new_messages_non_200(self):
        ch = self._make_channel(bluebubbles_password="pass")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        ch._http = mock_http
        await ch._check_new_messages()  # should not raise

    @pytest.mark.asyncio
    async def test_check_new_messages_dispatches_events(self):
        ch = self._make_channel(bluebubbles_password="pass")
        ch._last_ms = 1000
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "dateCreated": 2000,
                    "text": "Hello Angie",
                    "handle": {"address": "+15555550100"},
                }
            ]
        }
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        ch._http = mock_http
        with patch.object(ch, "_dispatch_event", new_callable=AsyncMock) as mock_dispatch:
            await ch._check_new_messages()
        mock_dispatch.assert_called_once_with("+15555550100", "Hello Angie")
        assert ch._last_ms == 2000
