"""Tests for angie.channels.base (ChannelManager, BaseChannel)."""

from unittest.mock import AsyncMock, MagicMock, patch

from angie.channels.base import BaseChannel, ChannelManager

# ── Concrete test channel ─────────────────────────────────────────────────────


class MockChannel(BaseChannel):
    channel_type = "mock"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send(self, user_id: str, text: str, **kwargs) -> None:
        pass

    async def mention_user(self, user_id: str, text: str, **kwargs) -> None:
        pass


class ErrorChannel(BaseChannel):
    channel_type = "error"

    async def start(self) -> None:
        raise RuntimeError("start failed")

    async def stop(self) -> None:
        raise RuntimeError("stop failed")

    async def send(self, user_id: str, text: str, **kwargs) -> None:
        raise RuntimeError("send failed")

    async def mention_user(self, user_id: str, text: str, **kwargs) -> None:
        pass


# ── ChannelManager tests ──────────────────────────────────────────────────────


def test_channel_manager_register():
    mgr = ChannelManager()
    ch = MockChannel()
    mgr.register(ch)
    assert mgr.get("mock") is ch


def test_channel_manager_get_nonexistent():
    mgr = ChannelManager()
    assert mgr.get("nonexistent") is None


async def test_channel_manager_start_all():
    mgr = ChannelManager()
    ch1 = MockChannel()
    ch1.start = AsyncMock()
    mgr.register(ch1)

    await mgr.start_all()
    ch1.start.assert_called_once()


async def test_channel_manager_start_all_error():
    mgr = ChannelManager()
    err_ch = ErrorChannel()
    mgr.register(err_ch)

    # Should not raise
    await mgr.start_all()


async def test_channel_manager_stop_all():
    mgr = ChannelManager()
    ch1 = MockChannel()
    ch1.stop = AsyncMock()
    mgr.register(ch1)

    await mgr.stop_all()
    ch1.stop.assert_called_once()


async def test_channel_manager_stop_all_error():
    mgr = ChannelManager()
    err_ch = ErrorChannel()
    mgr.register(err_ch)

    # Should not raise
    await mgr.stop_all()


async def test_channel_manager_send_specific_channel():
    mgr = ChannelManager()
    ch = MockChannel()
    ch.send = AsyncMock()
    mgr.register(ch)

    await mgr.send("user1", "hello", channel_type="mock")
    ch.send.assert_called_once_with("user1", "hello")


async def test_channel_manager_send_broadcast():
    mgr = ChannelManager()

    ch1 = MockChannel()
    ch1.send = AsyncMock()

    ch2 = MockChannel()
    ch2.channel_type = "mock2"
    ch2.send = AsyncMock()

    mgr.register(ch1)
    mgr.register(ch2)

    await mgr.send("user1", "broadcast message")

    ch1.send.assert_called_once_with("user1", "broadcast message")
    ch2.send.assert_called_once_with("user1", "broadcast message")


async def test_channel_manager_send_broadcast_error():
    mgr = ChannelManager()
    err_ch = ErrorChannel()
    mgr.register(err_ch)

    # Should not raise
    await mgr.send("user1", "hello")


async def test_channel_manager_send_unknown_channel_type():
    """When sending to an unknown channel type, it falls back to broadcast to all."""
    mgr = ChannelManager()
    ch = MockChannel()
    ch.send = AsyncMock()
    mgr.register(ch)

    # Sending to unknown channel type - channel type not in _channels, so no specific send
    # But the code only returns early if channel_type is found; otherwise broadcasts
    # So "unknown" type falls through to broadcast
    await mgr.send("user1", "hello", channel_type="unknown")
    # Falls through to broadcast: mock channel gets called
    ch.send.assert_called_once_with("user1", "hello")


# ── get_channel_manager / _build_manager tests ───────────────────────────────


def test_get_channel_manager_singleton():
    import angie.channels.base as base_mod

    old_mgr = base_mod._manager
    base_mod._manager = None

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.slack_bot_token = None
        mock_settings.discord_bot_token = None
        mock_settings.bluebubbles_url = None
        mock_settings.email_smtp_host = None
        mock_gs.return_value = mock_settings

        mgr1 = base_mod.get_channel_manager()
        mgr2 = base_mod.get_channel_manager()

    assert mgr1 is mgr2
    base_mod._manager = old_mgr


def test_build_manager_no_channels():
    import angie.channels.base as base_mod

    with patch("angie.config.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.slack_bot_token = None
        mock_settings.discord_bot_token = None
        mock_settings.bluebubbles_url = None
        mock_settings.email_smtp_host = None
        mock_gs.return_value = mock_settings

        mgr = base_mod._build_manager()

    assert isinstance(mgr, ChannelManager)
    assert len(mgr._channels) == 0


def test_build_manager_with_slack():
    import angie.channels.base as base_mod

    with (
        patch("angie.config.get_settings") as mock_gs,
        patch("angie.channels.slack.SlackChannel") as mock_slack_cls,
    ):
        mock_settings = MagicMock()
        mock_settings.slack_bot_token = "xoxb-token"
        mock_settings.discord_bot_token = None
        mock_settings.bluebubbles_url = None
        mock_settings.email_smtp_host = None
        mock_gs.return_value = mock_settings

        mock_slack = MagicMock()
        mock_slack.channel_type = "slack"
        mock_slack_cls.return_value = mock_slack

        mgr = base_mod._build_manager()

    assert "slack" in mgr._channels
