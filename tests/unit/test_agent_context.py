"""Tests for BaseAgent conversation context methods."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── _build_context_prompt tests ───────────────────────────────────────────────


@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
def test_build_context_prompt_with_history(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    history = [
        {"role": "user", "content": "What's the weather?", "agent_slug": ""},
        {"role": "assistant", "content": "It's 72°F and sunny.", "agent_slug": "weather"},
        {"role": "user", "content": "Now check my GitHub PRs", "agent_slug": ""},
    ]

    result = agent._build_context_prompt("check open PRs", history)

    assert "## Conversation Context" in result
    assert "[USER]: What's the weather?" in result
    assert "[weather]: It's 72°F and sunny." in result
    assert "[USER]: Now check my GitHub PRs" in result
    assert "## Your Task" in result
    assert "check open PRs" in result


@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
def test_build_context_prompt_empty_history(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    result = agent._build_context_prompt("check open PRs", [])

    assert result == "check open PRs"


@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
def test_build_context_prompt_assistant_no_slug(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()
    history = [
        {"role": "assistant", "content": "Hello!", "agent_slug": ""},
    ]

    result = agent._build_context_prompt("do something", history)
    assert "[ASSISTANT]: Hello!" in result


# ── get_conversation_history tests ────────────────────────────────────────────


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_get_conversation_history_returns_messages(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()

    # Mock the DB query
    mock_msg1 = MagicMock()
    mock_msg1.role.value = "user"
    mock_msg1.content = "hello"
    mock_msg1.agent_slug = None

    mock_msg2 = MagicMock()
    mock_msg2.role.value = "assistant"
    mock_msg2.content = "world"
    mock_msg2.agent_slug = "weather"

    # The query now uses DESC order so the DB returns newest-first.
    # Simulate that here: mock_msg2 (assistant, newer) comes before mock_msg1 (user, older).
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_msg2, mock_msg1]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    with patch("angie.db.session.get_session_factory", return_value=mock_factory):
        history = await agent.get_conversation_history("conv-123")

    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "hello", "agent_slug": ""}
    assert history[1] == {"role": "assistant", "content": "world", "agent_slug": "weather"}


@pytest.mark.asyncio
@patch("angie.config.get_settings")
@patch("angie.core.prompts.get_prompt_manager")
async def test_get_conversation_history_db_error_returns_empty(mock_pm, mock_gs):
    mock_gs.return_value = MagicMock()
    mock_pm.return_value = MagicMock()

    from angie.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "Dummy"
        slug = "dummy"
        description = "test"

        async def execute(self, task):
            return {}

    agent = DummyAgent()

    with patch("angie.db.session.get_session_factory", side_effect=Exception("DB down")):
        history = await agent.get_conversation_history("conv-123")

    assert history == []
