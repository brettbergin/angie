"""Web chat channel (WebSocket bridge)."""

from __future__ import annotations

import logging
from typing import Any

from angie.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class WebChatChannel(BaseChannel):
    channel_type = "web"

    def __init__(self) -> None:
        self._connections: dict[str, Any] = {}  # user_id -> websocket

    async def start(self) -> None:
        logger.info("Web chat channel ready")

    async def stop(self) -> None:
        self._connections.clear()

    def register_connection(self, user_id: str, websocket: Any) -> None:
        self._connections[user_id] = websocket

    def unregister_connection(self, user_id: str) -> None:
        self._connections.pop(user_id, None)

    async def send(self, user_id: str, text: str, **kwargs: Any) -> None:
        ws = self._connections.get(user_id)
        if ws:
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.warning("WebSocket send to %s failed: %s", user_id, e)
                self.unregister_connection(user_id)

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, f"@{user_id} {text}")
