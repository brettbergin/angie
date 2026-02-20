"""Slack channel adapter."""

from __future__ import annotations

import logging
from typing import Any

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)


class SlackChannel(BaseChannel):
    channel_type = "slack"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    async def start(self) -> None:
        from slack_sdk.web.async_client import AsyncWebClient

        self._client = AsyncWebClient(token=self.settings.slack_bot_token)
        # Verify connection
        await self._client.auth_test()
        logger.info("Slack channel connected")

    async def stop(self) -> None:
        self._client = None

    async def send(
        self, user_id: str, text: str, channel: str | None = None, **kwargs: Any
    ) -> None:
        if self._client is None:
            return
        target = channel or user_id
        await self._client.chat_postMessage(channel=target, text=text)

    async def mention_user(
        self, user_id: str, text: str, channel: str | None = None, **kwargs: Any
    ) -> None:
        await self.send(user_id, f"<@{user_id}> {text}", channel=channel)
