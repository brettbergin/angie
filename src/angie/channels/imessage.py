"""iMessage channel adapter via BlueBubbles REST API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 15  # seconds between BlueBubbles inbox polls


class IMessageChannel(BaseChannel):
    channel_type = "imessage"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._http: httpx.AsyncClient | None = None
        self._last_ms: int = int(time.time() * 1000)
        self._poll_task: asyncio.Task | None = None

    @property
    def _base_url(self) -> str:
        return f"{self.settings.bluebubbles_url}/api/v1"

    @property
    def _auth(self) -> dict[str, str]:
        return {"password": self.settings.bluebubbles_password or ""}

    async def start(self) -> None:
        self._http = httpx.AsyncClient(timeout=10.0)
        resp = await self._http.get(f"{self._base_url}/ping", params=self._auth)
        resp.raise_for_status()
        logger.info("BlueBubbles (iMessage) channel connected")
        self._poll_task = asyncio.create_task(self._poll_messages())

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self._http:
            await self._http.aclose()

    async def _poll_messages(self) -> None:
        """Poll BlueBubbles for new messages sent to the bot."""
        while True:
            try:
                await self._check_new_messages()
            except Exception as exc:
                logger.debug("iMessage poll error: %s", exc)
            await asyncio.sleep(POLL_INTERVAL)

    async def _check_new_messages(self) -> None:
        if not self._http:
            return
        params = {
            **self._auth,
            "after": self._last_ms,
            "limit": 50,
            "sort": "ASC",
            "where": '[{"statement":"message.is_from_me = 0","isDateValue":false}]',
        }
        resp = await self._http.get(f"{self._base_url}/message/query", params=params)
        if resp.status_code != 200:
            return
        data = resp.json()
        messages = data.get("data", [])
        for msg in messages:
            date_ms: int = msg.get("dateCreated", 0)
            if date_ms <= self._last_ms:
                continue
            text: str = msg.get("text", "") or ""
            handle: str = msg.get("handle", {}).get("address", "") if msg.get("handle") else ""
            if text.strip():
                logger.info("iMessage from %s: %s", handle, text[:80])
                await self._dispatch_event(handle, text.strip())
            self._last_ms = max(self._last_ms, date_ms)

    async def _dispatch_event(self, sender: str, text: str) -> None:
        from angie.core.events import AngieEvent, router
        from angie.models.event import EventType

        event = AngieEvent(
            type=EventType.CHANNEL_MESSAGE,
            user_id=sender,
            payload={"text": text, "handle": sender},
            source_channel="imessage",
        )
        await router.dispatch(event)

    async def send(self, user_id: str, text: str, handle: str | None = None, **kwargs: Any) -> None:
        if self._http is None:
            return
        target = handle or user_id
        payload = {"chatGuid": f"iMessage;-;{target}", "message": text, "method": "apple-script"}
        resp = await self._http.post(
            f"{self._base_url}/message/text",
            params=self._auth,
            json=payload,
        )
        resp.raise_for_status()

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, f"Hey! {text}", **kwargs)
