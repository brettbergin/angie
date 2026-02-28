"""Slack channel adapter — Socket Mode inbound + AsyncWebClient outbound."""

from __future__ import annotations

import asyncio
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
        self._socket_handler = None
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> None:
        from slack_sdk.web.async_client import AsyncWebClient

        self._client = AsyncWebClient(token=self.settings.slack_bot_token)
        await self._client.auth_test()
        logger.info("Slack channel connected")

        # Start Socket Mode listener if app token is configured
        if self.settings.slack_app_token:
            self._listen_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Listen for inbound messages via Slack Socket Mode."""
        from slack_sdk.socket_mode.aiohttp import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest

        app_token = self.settings.slack_app_token

        async def _process(client: SocketModeClient, req: SocketModeRequest) -> None:
            from slack_sdk.socket_mode.response import SocketModeResponse

            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

            if req.type != "events_api":
                return
            event = req.payload.get("event", {})
            if event.get("type") != "message" or event.get("subtype"):
                return

            text: str = event.get("text", "").strip()
            user_id: str = event.get("user", "")
            channel: str = event.get("channel", "")

            # Only respond when @-mentioned or in a DM
            bot_id = (await self._client.auth_test()).get("user_id", "")
            if not (f"<@{bot_id}>" in text or channel.startswith("D")):
                return

            # Strip the mention prefix
            clean_text = text.replace(f"<@{bot_id}>", "").strip()
            logger.info("Slack inbound from %s: %s", user_id, clean_text)

            await self._dispatch_event(
                user_id=user_id,
                text=clean_text,
                channel=channel,
                thread_ts=event.get("ts"),
            )

        sm_client = SocketModeClient(app_token=app_token, web_client=self._client)
        sm_client.socket_mode_request_listeners.append(_process)
        await sm_client.connect()
        logger.info("Slack Socket Mode listener started")
        # Keep alive
        while True:
            await asyncio.sleep(30)

    async def _dispatch_event(
        self, user_id: str, text: str, channel: str, thread_ts: str | None = None
    ) -> None:
        """Convert inbound message to an AngieEvent and dispatch it."""
        from angie.core.events import AngieEvent, router
        from angie.models.event import EventType

        payload: dict[str, Any] = {"text": text, "channel": channel}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        event = AngieEvent(
            type=EventType.CHANNEL_MESSAGE,
            user_id=user_id,
            payload=payload,
            source_channel="slack",
        )
        await router.dispatch(event)

    async def stop(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
        self._client = None

    async def send(
        self,
        user_id: str,
        text: str,
        channel: str | None = None,
        thread_ts: str | None = None,
        **kwargs: Any,
    ) -> None:
        if self._client is None:
            return
        target = channel or user_id
        msg_kwargs: dict[str, Any] = {"channel": target, "text": text}
        if thread_ts:
            msg_kwargs["thread_ts"] = thread_ts
        await self._client.chat_postMessage(**msg_kwargs)

    async def health_check(self) -> bool:
        """Verify Slack connection is alive via auth.test."""
        if self._client is None:
            return False
        try:
            result = await self._client.auth_test()
            return result.get("ok", False)
        except Exception:
            return False

    async def mention_user(
        self, user_id: str, text: str, channel: str | None = None, **kwargs: Any
    ) -> None:
        await self.send(user_id, f"<@{user_id}> {text}", channel=channel)
