"""Feedback system — log outcomes and notify users through their channel."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_thread_kwargs(
    task_dict: dict[str, Any] | None,
    source_channel: str | None = None,
) -> dict[str, Any]:
    """Extract Slack/Discord thread-context kwargs from a task dict.

    Shared by FeedbackManager._send and workers._send_reply to avoid
    duplicating the channel-specific threading logic.
    """
    kwargs: dict[str, Any] = {}
    if not task_dict:
        return kwargs
    input_data = task_dict.get("input_data", {})
    channel = source_channel or task_dict.get("source_channel")
    if channel == "slack":
        if input_data.get("channel"):
            kwargs["channel"] = input_data["channel"]
        if input_data.get("thread_ts"):
            kwargs["thread_ts"] = input_data["thread_ts"]
    elif channel == "discord":
        if input_data.get("channel_id"):
            kwargs["channel_id"] = input_data["channel_id"]
        if input_data.get("message_id"):
            kwargs["reply_to_message_id"] = input_data["message_id"]
    return kwargs


class FeedbackManager:
    """Routes success/failure feedback to the originating channel."""

    async def send_success(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
        task_id: str | None = None,
        task_dict: dict[str, Any] | None = None,
    ) -> None:
        logger.info(
            "[FEEDBACK OK] user=%s channel=%s task=%s | %s", user_id, channel, task_id, message
        )
        await self._send(user_id, message, channel, task_dict=task_dict)

    async def send_failure(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
        task_id: str | None = None,
        error: str | None = None,
        task_dict: dict[str, Any] | None = None,
    ) -> None:
        text = message
        if error:
            text += f"\n```{error}```"
        logger.error(
            "[FEEDBACK ERR] user=%s channel=%s task=%s | %s", user_id, channel, task_id, message
        )
        await self._send(user_id, text, channel, task_dict=task_dict)

    async def send_mention(
        self,
        user_id: str,
        message: str,
        channel: str | None = None,
        **kwargs: Any,
    ) -> None:
        """@-mention the user through their preferred channel."""
        logger.info("[FEEDBACK MENTION] user=%s channel=%s | %s", user_id, channel, message)
        await self._send(user_id, f"Hey @{user_id} — {message}", channel)

    async def _send(
        self,
        user_id: str,
        text: str,
        channel: str | None,
        task_dict: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch to the appropriate channel adapter with thread context."""
        from angie.channels.base import get_channel_manager

        mgr = get_channel_manager()
        kwargs = extract_thread_kwargs(task_dict)

        await mgr.send(user_id=user_id, text=text, channel_type=channel, **kwargs)


_feedback: FeedbackManager | None = None


def get_feedback() -> FeedbackManager:
    global _feedback
    if _feedback is None:
        _feedback = FeedbackManager()
    return _feedback
