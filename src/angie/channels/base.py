"""BaseChannel interface and channel manager."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseChannel(ABC):
    """Abstract base for all communication channel adapters."""

    channel_type: str  # e.g. "slack", "discord", "imessage", "email", "web"

    @abstractmethod
    async def start(self) -> None:
        """Connect to the platform and begin listening."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect cleanly."""
        ...

    @abstractmethod
    async def send(self, user_id: str, text: str, **kwargs: Any) -> None:
        """Send a message to a user."""
        ...

    @abstractmethod
    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        """@-mention a user with a message."""
        ...

    async def health_check(self) -> bool:
        """Return True if the channel connection is healthy.

        Subclasses should override with platform-specific checks.
        """
        return True


class ChannelManager:
    """Manages the lifecycle and routing of all active channels."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.channel_type] = channel
        logger.debug("Registered channel: %s", channel.channel_type)

    async def start_all(self) -> None:
        for ch in self._channels.values():
            try:
                await ch.start()
                logger.info("Channel started: %s", ch.channel_type)
            except Exception as e:
                logger.warning("Channel %s failed to start: %s", ch.channel_type, e)

    async def stop_all(self) -> None:
        for ch in self._channels.values():
            try:
                await ch.stop()
            except Exception:
                pass

    async def send(
        self, user_id: str, text: str, channel_type: str | None = None, **kwargs: Any
    ) -> None:
        if channel_type and channel_type in self._channels:
            await self._channels[channel_type].send(user_id, text, **kwargs)
            return
        # Broadcast to all enabled channels if no specific type given
        for ch in self._channels.values():
            try:
                await ch.send(user_id, text, **kwargs)
            except Exception as e:
                logger.warning("Channel %s send failed: %s", ch.channel_type, e)

    def get(self, channel_type: str) -> BaseChannel | None:
        return self._channels.get(channel_type)


_manager: ChannelManager | None = None


def get_channel_manager() -> ChannelManager:
    global _manager
    if _manager is None:
        _manager = _build_manager()
    return _manager


def _build_manager() -> ChannelManager:
    """Instantiate and register all configured channels."""
    from angie.config import get_settings

    settings = get_settings()
    mgr = ChannelManager()

    if settings.slack_bot_token:
        from angie.channels.slack import SlackChannel

        mgr.register(SlackChannel())

    if settings.discord_bot_token:
        from angie.channels.discord import DiscordChannel

        mgr.register(DiscordChannel())

    if settings.bluebubbles_url:
        from angie.channels.imessage import IMessageChannel

        mgr.register(IMessageChannel())

    if settings.email_smtp_host:
        from angie.channels.email import EmailChannel

        mgr.register(EmailChannel())

    return mgr
