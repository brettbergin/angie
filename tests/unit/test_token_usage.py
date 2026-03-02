"""Tests for token usage tracking: pricing, recording, and model."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── estimate_cost ─────────────────────────────────────────────────────────────


def test_estimate_cost_exact_match():
    from angie.core.token_usage import estimate_cost

    # gpt-4o: $2.50/1M input, $10.00/1M output
    cost = estimate_cost("openai", "gpt-4o", 1000, 500)
    expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_estimate_cost_prefix_match():
    from angie.core.token_usage import estimate_cost

    # "gpt-4o-2024-08-06" should match prefix "gpt-4o"
    cost = estimate_cost("openai", "gpt-4o-2024-08-06", 1000, 500)
    expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_estimate_cost_unknown_model():
    from angie.core.token_usage import estimate_cost

    cost = estimate_cost("unknown-provider", "unknown-model", 1000, 500)
    assert cost == 0.0


def test_estimate_cost_zero_tokens():
    from angie.core.token_usage import estimate_cost

    cost = estimate_cost("openai", "gpt-4o", 0, 0)
    assert cost == 0.0


def test_estimate_cost_anthropic():
    from angie.core.token_usage import estimate_cost

    cost = estimate_cost("anthropic", "claude-sonnet-4-20250514", 10000, 5000)
    # Prefix match: "claude-sonnet-4"
    expected = (10000 * 3.00 + 5000 * 15.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_estimate_cost_github_models():
    from angie.core.token_usage import estimate_cost

    cost = estimate_cost("github", "openai/gpt-4o", 2000, 1000)
    expected = (2000 * 2.50 + 1000 * 10.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


# ── record_usage ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_usage_creates_record():
    from angie.core.token_usage import record_usage

    mock_usage = MagicMock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50
    mock_usage.total_tokens = 150
    mock_usage.requests = 1

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock()
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_context

    with (
        patch("angie.db.session.get_session_factory", return_value=mock_factory),
        patch("angie.core.token_usage._get_provider_and_model", return_value=("openai", "gpt-4o")),
    ):
        await record_usage(
            user_id="user-1",
            agent_slug="weather",
            usage=mock_usage,
            source="agent_execute",
            task_id="task-1",
            conversation_id="conv-1",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    record = mock_session.add.call_args[0][0]
    assert record.user_id == "user-1"
    assert record.agent_slug == "weather"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.source == "agent_execute"
    assert record.task_id == "task-1"
    assert record.conversation_id == "conv-1"
    assert record.estimated_cost_usd > 0


@pytest.mark.asyncio
async def test_record_usage_handles_failure():
    """record_usage should not raise even if DB write fails."""
    from angie.core.token_usage import record_usage

    mock_usage = MagicMock()
    mock_usage.input_tokens = 10
    mock_usage.output_tokens = 5
    mock_usage.total_tokens = 15
    mock_usage.requests = 1

    with patch(
        "angie.db.session.get_session_factory",
        side_effect=RuntimeError("DB down"),
    ):
        # Should not raise
        await record_usage(
            user_id="user-1",
            agent_slug="test",
            usage=mock_usage,
            source="test",
        )


# ── TokenUsage model ─────────────────────────────────────────────────────────


def test_token_usage_model_repr():
    from angie.models.token_usage import TokenUsage

    record = TokenUsage(
        id="test-id",
        source="agent_execute",
        total_tokens=500,
    )
    r = repr(record)
    assert "test-id" in r
    assert "agent_execute" in r
    assert "500" in r


def test_token_usage_model_with_values():
    from angie.models.token_usage import TokenUsage

    record = TokenUsage(
        source="chat_ws",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        request_count=1,
        tool_call_count=0,
        estimated_cost_usd=0.001,
    )
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.request_count == 1
    assert record.tool_call_count == 0
    assert record.estimated_cost_usd == 0.001
