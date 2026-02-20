"""Feedback system — log outcomes and notify users through their channel."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class FeedbackManager:
    """Routes success/failure feedback to the originating channel."""

    async def send_success(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
        task_id: str | None = None,
    ) -> None:
        logger.info("[FEEDBACK OK] user=%s channel=%s task=%s | %s", user_id, channel, task_id, message)
        await self._send(user_id, f"✅ {message}", channel)

    async def send_failure(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
        task_id: str | None = None,
        error: str | None = None,
    ) -> None:
        text = f"❌ {message}"
        if error:
            text += f"\n```{error}```"
        logger.error("[FEEDBACK ERR] user=%s channel=%s task=%s | %s", user_id, channel, task_id, message)
        await self._send(user_id, text, channel)

    async def send_mention(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
    ) -> None:
        """@-mention the user through their preferred channel."""
        logger.info("[FEEDBACK MENTION] user=%s channel=%s | %s", user_id, channel, message)
        await self._send(user_id, f"Hey @{user_id} — {message}", channel)

    async def _send(self, user_id: str, text: str, channel: str | None) -> None:
        """Dispatch to the appropriate channel adapter."""
        from angie.channels.base import get_channel_manager
        mgr = get_channel_manager()
        await mgr.send(user_id=user_id, text=text, channel_type=channel)


_feedback: FeedbackManager | None = None


def get_feedback() -> FeedbackManager:
    global _feedback
    if _feedback is None:
        _feedback = FeedbackManager()
    return _feedback
