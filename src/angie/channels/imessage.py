"""iMessage channel adapter via BlueBubbles REST API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from angie.channels.base import BaseChannel
from angie.config import get_settings

logger = logging.getLogger(__name__)


class IMessageChannel(BaseChannel):
    channel_type = "imessage"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._http: httpx.AsyncClient | None = None

    @property
    def _base_url(self) -> str:
        return f"{self.settings.bluebubbles_url}/api/v1"

    @property
    def _auth(self) -> dict[str, str]:
        return {"password": self.settings.bluebubbles_password or ""}

    async def start(self) -> None:
        self._http = httpx.AsyncClient(timeout=10.0)
        # Verify connection
        resp = await self._http.get(f"{self._base_url}/ping", params=self._auth)
        resp.raise_for_status()
        logger.info("BlueBubbles (iMessage) channel connected")

    async def stop(self) -> None:
        if self._http:
            await self._http.aclose()

    async def send(self, user_id: str, text: str, handle: str | None = None, **kwargs: Any) -> None:
        if self._http is None:
            return
        # handle is the iMessage address (phone number or email)
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
