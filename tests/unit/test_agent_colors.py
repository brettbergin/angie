"""Tests for agent_slug threading through ChatMessage and workers."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def test_chat_message_accepts_agent_slug():
    """ChatMessage model should accept agent_slug."""
    from angie.models.conversation import ChatMessage, MessageRole

    msg = ChatMessage(
        conversation_id="conv-1",
        role=MessageRole.ASSISTANT,
        content="Done",
        agent_slug="github",
    )
    assert msg.agent_slug == "github"


def test_chat_message_agent_slug_none_by_default():
    """ChatMessage with no agent_slug should default to None (backwards compat)."""
    from angie.models.conversation import ChatMessage, MessageRole

    msg = ChatMessage(
        conversation_id="conv-1",
        role=MessageRole.ASSISTANT,
        content="Hello",
    )
    assert msg.agent_slug is None


@pytest.mark.asyncio
async def test_deliver_chat_result_passes_agent_slug():
    """_deliver_chat_result should persist and publish agent_slug via Redis."""
    from angie.queue.workers import _deliver_chat_result

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    mock_publish = MagicMock()

    with (
        patch("angie.db.session.get_session_factory", return_value=mock_factory),
        patch("angie.channels.web_chat.WebChatChannel.publish_result_sync", mock_publish),
    ):
        await _deliver_chat_result("conv-1", "user-1", "Result text", agent_slug="weather")

    # Verify ChatMessage was created with agent_slug
    add_call = mock_session.add.call_args[0][0]
    assert add_call.agent_slug == "weather"

    # Verify Redis publish includes agent_slug
    mock_publish.assert_called_once_with(
        "user-1",
        "Result text",
        "conv-1",
        agent_slug="weather",
    )


@pytest.mark.asyncio
async def test_deliver_chat_result_agent_slug_none():
    """_deliver_chat_result with no agent_slug should still work."""
    from angie.queue.workers import _deliver_chat_result

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    mock_publish = MagicMock()

    with (
        patch("angie.db.session.get_session_factory", return_value=mock_factory),
        patch("angie.channels.web_chat.WebChatChannel.publish_result_sync", mock_publish),
    ):
        await _deliver_chat_result("conv-1", "user-1", "Result text")

    add_call = mock_session.add.call_args[0][0]
    assert add_call.agent_slug is None


@pytest.mark.asyncio
async def test_web_chat_send_includes_agent_slug():
    """WebChatChannel.send() should include agent_slug in JSON payload."""
    from angie.channels.web_chat import WebChatChannel

    channel = WebChatChannel()
    mock_ws = AsyncMock()
    channel.register_connection("user-1", mock_ws)

    await channel.send(
        "user-1",
        "hello",
        conversation_id="conv-1",
        agent_slug="github",
    )

    sent_text = mock_ws.send_text.call_args[0][0]
    payload = json.loads(sent_text)
    assert payload["agent_slug"] == "github"
    assert payload["type"] == "task_result"


@pytest.mark.asyncio
async def test_web_chat_send_omits_agent_slug_when_none():
    """WebChatChannel.send() should not include agent_slug when None."""
    from angie.channels.web_chat import WebChatChannel

    channel = WebChatChannel()
    mock_ws = AsyncMock()
    channel.register_connection("user-1", mock_ws)

    await channel.send(
        "user-1",
        "hello",
        conversation_id="conv-1",
    )

    sent_text = mock_ws.send_text.call_args[0][0]
    payload = json.loads(sent_text)
    assert "agent_slug" not in payload
