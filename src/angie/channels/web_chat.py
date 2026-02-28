"""Web chat channel (WebSocket bridge)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from angie.channels.base import BaseChannel

logger = logging.getLogger(__name__)

# Module-level sync Redis client — lazily initialised, reused across calls.
_sync_redis_client = None
_sync_redis_lock = __import__("threading").Lock()


def _get_sync_redis():
    """Return a lazily-initialised, module-level sync Redis client."""
    global _sync_redis_client
    if _sync_redis_client is None:
        with _sync_redis_lock:
            if _sync_redis_client is None:
                import redis

                from angie.config import get_settings

                settings = get_settings()
                _sync_redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis_client


def _build_task_result_payload(
    text: str,
    conversation_id: str,
    agent_slug: str | None = None,
) -> dict[str, Any]:
    """Build the standard task_result JSON payload."""
    payload: dict[str, Any] = {
        "message_id": str(uuid.uuid4()),
        "content": text,
        "role": "assistant",
        "conversation_id": conversation_id,
        "type": "task_result",
    }
    if agent_slug:
        payload["agent_slug"] = agent_slug
    return payload


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

    async def send(
        self,
        user_id: str,
        text: str,
        *,
        conversation_id: str | None = None,
        agent_slug: str | None = None,
        **kwargs: Any,
    ) -> None:
        ws = self._connections.get(user_id)
        if ws:
            try:
                if conversation_id:
                    payload_dict = _build_task_result_payload(text, conversation_id, agent_slug)
                    await ws.send_text(json.dumps(payload_dict))
                else:
                    await ws.send_text(text)
            except Exception as e:
                logger.warning("WebSocket send to %s failed: %s", user_id, e)
                self.unregister_connection(user_id)

    # ── Redis pub/sub bridge for cross-process task result delivery ────────

    @staticmethod
    def redis_channel(user_id: str) -> str:
        """Return the Redis pub/sub channel name for a given user."""
        return f"angie:task_results:{user_id}"

    @staticmethod
    async def listen_redis(user_id: str, websocket: Any) -> None:
        """Subscribe to Redis and forward task results to the WebSocket.

        Runs as a long-lived asyncio task; cancelled on WS disconnect.
        """
        import redis.asyncio as aioredis

        from angie.config import get_settings

        settings = get_settings()
        channel_name = WebChatChannel.redis_channel(user_id)
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(channel_name)
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    logger.debug("Redis→WS forward failed for %s", user_id)
                    break
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await client.aclose()

    @staticmethod
    def publish_result_sync(
        user_id: str,
        text: str,
        conversation_id: str,
        agent_slug: str | None = None,
    ) -> None:
        """Publish a task result to Redis from a sync context (Celery worker)."""
        channel_name = WebChatChannel.redis_channel(user_id)
        payload = _build_task_result_payload(text, conversation_id, agent_slug)
        client = _get_sync_redis()
        client.publish(channel_name, json.dumps(payload))

    async def mention_user(self, user_id: str, text: str, **kwargs: Any) -> None:
        await self.send(user_id, f"@{user_id} {text}")
