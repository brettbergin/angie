"""Discord channel adapter."""

from __future__ import annotations

import logging
from typing import Any

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)


class DiscordChannel(BaseChannel):
    channel_type = "discord"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    async def start(self) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        logger.info("Discord channel initialized (call connect separately for full bot)")

    async def stop(self) -> None:
        if self._client and not self._client.is_closed():
            await self._client.close()

    async def send(self, user_id: str, text: str, channel_id: int | None = None, **kwargs: Any) -> None:
        if self._client is None:
            return
        if channel_id:
            channel = self._client.get_channel(channel_id)
            if channel:
                await channel.send(text)  # type: ignore[union-attr]
                return
        # DM the user
        user = await self._client.fetch_user(int(user_id))
        await user.send(text)

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, f"<@{user_id}> {text}", **kwargs)
