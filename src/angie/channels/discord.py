"""Discord channel adapter — bot with inbound on_message + send/DM."""

from __future__ import annotations

import asyncio
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
        self._bot_task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.settings.discord_bot_token:
            logger.warning("Discord bot token not configured")
            return
        self._bot_task = asyncio.create_task(self._run_bot())
        logger.info("Discord channel starting")

    async def _run_bot(self) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self._client = client

        @client.event
        async def on_ready() -> None:
            logger.info("Discord bot ready as %s", client.user)

        @client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == client.user:
                return

            # Respond when @-mentioned or in a DM channel
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = client.user in message.mentions if client.user else False

            if not (is_dm or is_mentioned):
                return

            text = message.content
            # Strip the mention prefix
            if client.user:
                text = text.replace(f"<@{client.user.id}>", "").strip()
                text = text.replace(f"<@!{client.user.id}>", "").strip()

            logger.info("Discord inbound from %s: %s", message.author.id, text)
            await self._dispatch_event(
                user_id=str(message.author.id),
                text=text,
                channel_id=str(message.channel.id),
            )

        try:
            await client.start(self.settings.discord_bot_token)
        except asyncio.CancelledError:
            await client.close()

    async def _dispatch_event(self, user_id: str, text: str, channel_id: str) -> None:
        from angie.core.events import AngieEvent, router
        from angie.models.event import EventType

        event = AngieEvent(
            type=EventType.CHANNEL_MESSAGE,
            user_id=user_id,
            payload={"text": text, "channel_id": channel_id},
            source_channel="discord",
        )
        await router.dispatch(event)

    async def stop(self) -> None:
        if self._client and not self._client.is_closed():
            await self._client.close()
        if self._bot_task:
            self._bot_task.cancel()

    async def send(
        self, user_id: str, text: str, channel_id: int | str | None = None, **kwargs: Any
    ) -> None:
        if self._client is None:
            return
        if channel_id:
            channel = self._client.get_channel(int(channel_id))
            if channel:
                await channel.send(text)  # type: ignore[union-attr]
                return
        # Fall back to DM
        try:
            user = await self._client.fetch_user(int(user_id))
            await user.send(text)
        except Exception as exc:
            logger.warning("Discord DM failed: %s", exc)

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, f"<@{user_id}> {text}", **kwargs)
