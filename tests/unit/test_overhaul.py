"""Tests for the major overhaul: threading, feedback, subscriptions, initiative,
health monitoring, confidence scoring, and LLM routing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from angie.agents.base import BaseAgent
from angie.agents.registry import AgentRegistry

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── Test agent for reuse ─────────────────────────────────────────────────────


class MockAgent(BaseAgent):
    name: ClassVar[str] = "MockAgent"
    slug: ClassVar[str] = "mock"
    description: ClassVar[str] = "A mock agent for testing"
    capabilities: ClassVar[list[str]] = ["mock", "test"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "summary": "Done"}


# ── Phase 1: Threading ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_send_with_thread_ts():
    """Slack send() passes thread_ts to chat_postMessage."""
    from angie.channels.slack import SlackChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test"
        mock_settings.return_value.slack_app_token = ""
        ch = SlackChannel()
        ch._client = AsyncMock()
        await ch.send("U123", "hello", channel="C456", thread_ts="1234567890.123456")
        ch._client.chat_postMessage.assert_called_once_with(
            channel="C456", text="hello", thread_ts="1234567890.123456"
        )


@pytest.mark.asyncio
async def test_slack_send_without_thread_ts():
    """Slack send() works without thread_ts."""
    from angie.channels.slack import SlackChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test"
        mock_settings.return_value.slack_app_token = ""
        ch = SlackChannel()
        ch._client = AsyncMock()
        await ch.send("U123", "hello", channel="C456")
        ch._client.chat_postMessage.assert_called_once_with(channel="C456", text="hello")


@pytest.mark.asyncio
async def test_slack_dispatch_includes_thread_ts():
    """Slack _dispatch_event includes thread_ts in payload."""
    from angie.channels.slack import SlackChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test"
        mock_settings.return_value.slack_app_token = ""
        ch = SlackChannel()

    with patch("angie.core.events.router.dispatch", new_callable=AsyncMock) as mock_dispatch:
        await ch._dispatch_event(user_id="U123", text="hi", channel="C456", thread_ts="12345.678")
        event = mock_dispatch.call_args[0][0]
        assert event.payload["thread_ts"] == "12345.678"
        assert event.payload["channel"] == "C456"


@pytest.mark.asyncio
async def test_discord_dispatch_includes_message_id():
    """Discord _dispatch_event includes message_id in payload."""
    from angie.channels.discord import DiscordChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.discord_bot_token = "test-token"
        ch = DiscordChannel()

    with patch("angie.core.events.router.dispatch", new_callable=AsyncMock) as mock_dispatch:
        await ch._dispatch_event(user_id="12345", text="hi", channel_id="67890", message_id="99999")
        event = mock_dispatch.call_args[0][0]
        assert event.payload["message_id"] == "99999"
        assert event.payload["channel_id"] == "67890"


@pytest.mark.asyncio
async def test_send_reply_extracts_slack_thread_context():
    """_send_reply extracts thread_ts from task_dict for Slack."""
    from angie.queue.workers import _send_reply

    mock_mgr = MagicMock()
    mock_mgr.send = AsyncMock()

    task_dict = {
        "input_data": {"channel": "C456", "thread_ts": "12345.678"},
        "source_channel": "slack",
    }

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        await _send_reply("slack", "U123", "hello", task_dict)

    mock_mgr.send.assert_called_once_with(
        "U123", "hello", channel_type="slack", channel="C456", thread_ts="12345.678"
    )


@pytest.mark.asyncio
async def test_send_reply_extracts_discord_thread_context():
    """_send_reply extracts message_id from task_dict for Discord."""
    from angie.queue.workers import _send_reply

    mock_mgr = MagicMock()
    mock_mgr.send = AsyncMock()

    task_dict = {
        "input_data": {"channel_id": "67890", "message_id": "99999"},
        "source_channel": "discord",
    }

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        await _send_reply("discord", "12345", "hello", task_dict)

    mock_mgr.send.assert_called_once_with(
        "12345", "hello", channel_type="discord", channel_id="67890", reply_to_message_id="99999"
    )


@pytest.mark.asyncio
async def test_send_reply_backward_compat_no_task_dict():
    """_send_reply works without task_dict (backward compatible)."""
    from angie.queue.workers import _send_reply

    mock_mgr = MagicMock()
    mock_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_mgr):
        await _send_reply("slack", "U123", "hello")

    mock_mgr.send.assert_called_once_with("U123", "hello", channel_type="slack")


@pytest.mark.asyncio
async def test_channel_manager_passes_kwargs():
    """ChannelManager.send passes **kwargs to channel.send."""
    from angie.channels.base import ChannelManager

    mgr = ChannelManager()
    mock_channel = AsyncMock()
    mock_channel.channel_type = "slack"
    mgr._channels["slack"] = mock_channel

    await mgr.send("U123", "hi", channel_type="slack", thread_ts="12345.678")
    mock_channel.send.assert_called_once_with("U123", "hi", thread_ts="12345.678")


# ── Phase 1: Feedback ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_send_success_with_thread_context():
    """FeedbackManager passes thread context from task_dict."""
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    task_dict = {
        "source_channel": "slack",
        "input_data": {"channel": "C456", "thread_ts": "12345.678"},
    }

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_success("user1", "Done", channel="slack", task_dict=task_dict)

    call_kwargs = mock_channel_mgr.send.call_args.kwargs
    assert call_kwargs.get("channel") == "C456"
    assert call_kwargs.get("thread_ts") == "12345.678"


@pytest.mark.asyncio
async def test_feedback_send_failure_with_task_dict():
    """FeedbackManager send_failure accepts task_dict."""
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_failure("user1", "Oops", channel="slack", task_dict=None)

    mock_channel_mgr.send.assert_called_once()


# ── Phase 3: Subscriptions ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscription_manager_subscribe_and_notify():
    """SubscriptionManager dispatches to registered callbacks."""
    from angie.core.events import AngieEvent
    from angie.core.subscriptions import SubscriptionManager
    from angie.models.event import EventType

    mgr = SubscriptionManager()
    called = []

    async def on_complete(event):
        called.append(event)

    mgr.subscribe(EventType.TASK_COMPLETE, on_complete)
    assert mgr.subscription_count == 1

    event = AngieEvent(type=EventType.TASK_COMPLETE, payload={"task_id": "t1"})
    await mgr.notify(event)

    assert len(called) == 1
    assert called[0].payload["task_id"] == "t1"


@pytest.mark.asyncio
async def test_subscription_manager_no_match():
    """SubscriptionManager does nothing for unsubscribed event types."""
    from angie.core.events import AngieEvent
    from angie.core.subscriptions import SubscriptionManager
    from angie.models.event import EventType

    mgr = SubscriptionManager()
    called = []

    async def on_complete(event):
        called.append(event)

    mgr.subscribe(EventType.TASK_COMPLETE, on_complete)

    event = AngieEvent(type=EventType.TASK_FAILED, payload={})
    await mgr.notify(event)

    assert len(called) == 0


@pytest.mark.asyncio
async def test_subscription_manager_callback_error_doesnt_propagate():
    """SubscriptionManager logs but doesn't raise on callback errors."""
    from angie.core.events import AngieEvent
    from angie.core.subscriptions import SubscriptionManager
    from angie.models.event import EventType

    mgr = SubscriptionManager()

    async def bad_callback(event):
        raise RuntimeError("boom")

    mgr.subscribe(EventType.TASK_COMPLETE, bad_callback)

    event = AngieEvent(type=EventType.TASK_COMPLETE, payload={})
    await mgr.notify(event)  # Should not raise


def test_subscription_manager_singleton():
    import angie.core.subscriptions as sub_mod
    from angie.core.subscriptions import get_subscription_manager

    sub_mod._manager = None
    m1 = get_subscription_manager()
    m2 = get_subscription_manager()
    assert m1 is m2
    sub_mod._manager = None


# ── Phase 3: Initiative Engine ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initiative_engine_runs_scanners():
    """InitiativeEngine calls scan() on registered scanners."""
    from angie.core.initiative import InitiativeEngine, Scanner, Suggestion

    class TestScanner(Scanner):
        name = "test"

        async def scan(self):
            return [Suggestion(user_id="u1", message="Test suggestion")]

    engine = InitiativeEngine()
    engine.register_scanner(TestScanner())

    with patch.object(engine, "_surface_suggestion", new_callable=AsyncMock) as mock_surface:
        await engine._run_scans()

    mock_surface.assert_called_once()
    assert mock_surface.call_args[0][0].message == "Test suggestion"


@pytest.mark.asyncio
async def test_initiative_engine_scanner_error_doesnt_propagate():
    """InitiativeEngine catches scanner errors."""
    from angie.core.initiative import InitiativeEngine, Scanner

    class BrokenScanner(Scanner):
        name = "broken"

        async def scan(self):
            raise RuntimeError("scanner died")

    engine = InitiativeEngine()
    engine.register_scanner(BrokenScanner())
    await engine._run_scans()  # Should not raise


# ── Phase 4: Health ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_slack_health_check_success():
    """SlackChannel health_check returns True when auth_test succeeds."""
    from angie.channels.slack import SlackChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test"
        mock_settings.return_value.slack_app_token = ""
        ch = SlackChannel()
        ch._client = AsyncMock()
        ch._client.auth_test.return_value = {"ok": True}
        assert await ch.health_check() is True


@pytest.mark.asyncio
async def test_slack_health_check_no_client():
    """SlackChannel health_check returns False when client is None."""
    from angie.channels.slack import SlackChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.slack_bot_token = "xoxb-test"
        mock_settings.return_value.slack_app_token = ""
        ch = SlackChannel()
        ch._client = None
        assert await ch.health_check() is False


@pytest.mark.asyncio
async def test_discord_health_check_ready():
    """DiscordChannel health_check returns True when client is ready."""
    from angie.channels.discord import DiscordChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.discord_bot_token = "test-token"
        ch = DiscordChannel()
        ch._client = MagicMock()
        ch._client.is_ready.return_value = True
        ch._client.is_closed.return_value = False
        assert await ch.health_check() is True


@pytest.mark.asyncio
async def test_discord_health_check_no_client():
    """DiscordChannel health_check returns False when client is None."""
    from angie.channels.discord import DiscordChannel

    with patch("angie.config.get_settings") as mock_settings:
        mock_settings.return_value.discord_bot_token = "test-token"
        ch = DiscordChannel()
        ch._client = None
        assert await ch.health_check() is False


# ── Phase 5: Confidence Scoring ──────────────────────────────────────────────


def test_confidence_explicit_slug_match():
    """confidence() returns 1.0 for explicit slug match."""
    agent = MockAgent()
    assert agent.confidence({"agent_slug": "mock"}) == 1.0


def test_confidence_explicit_slug_mismatch():
    """confidence() returns 0.0 for different slug."""
    agent = MockAgent()
    assert agent.confidence({"agent_slug": "other"}) == 0.0


def test_confidence_keyword_match():
    """confidence() scores based on capability keywords."""
    agent = MockAgent()
    score = agent.confidence({"title": "run a mock test", "input_data": {}})
    assert score > 0.0
    assert score <= 0.8


def test_confidence_no_match():
    """confidence() returns 0.0 when no keywords match."""
    agent = MockAgent()
    score = agent.confidence({"title": "unrelated task xyz", "input_data": {}})
    assert score == 0.0


def test_confidence_no_capabilities():
    """confidence() returns 0.0 for agent with no capabilities."""

    class NoCapsAgent(BaseAgent):
        name: ClassVar[str] = "NoCaps"
        slug: ClassVar[str] = "nocaps"
        description: ClassVar[str] = "Agent with no capabilities"
        capabilities: ClassVar[list[str]] = []

        async def execute(self, task):
            return {}

    agent = NoCapsAgent()
    assert agent.confidence({"title": "anything"}) == 0.0


# ── Phase 5: Registry Confidence Routing ─────────────────────────────────────


def test_registry_resolve_uses_confidence():
    """Registry resolve uses confidence scoring."""
    registry = AgentRegistry()
    registry.register(MockAgent())
    registry._loaded = True

    task = {"title": "run a mock test", "input_data": {}}

    with patch.object(registry, "_llm_route_sync", return_value=None):
        agent = registry.resolve(task)

    assert agent is not None
    assert agent.slug == "mock"


def test_registry_resolve_falls_to_llm_when_low_confidence():
    """Registry calls LLM route when all confidence scores < 0.5."""
    registry = AgentRegistry()
    registry.register(MockAgent())
    registry._loaded = True

    task = {"title": "something completely unrelated xyz", "input_data": {}}

    with patch.object(registry, "_llm_route_sync", return_value=None) as mock_llm:
        agent = registry.resolve(task)

    mock_llm.assert_called_once()
    assert agent is None


# ── Phase 5: Graceful No-Agent Handling ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_task_no_agent_graceful():
    """_run_task returns helpful message when no agent matches."""
    from angie.queue.workers import _run_task

    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = None
    mock_registry.list_all.return_value = [MockAgent()]

    with (
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
        patch("angie.queue.workers._send_reply", new_callable=AsyncMock) as mock_reply,
        patch("angie.queue.workers._update_task_in_db", new_callable=AsyncMock),
        patch("angie.queue.workers.reset_engine"),
    ):
        result = await _run_task(
            {
                "id": "task-1",
                "title": "unknown stuff",
                "user_id": "u1",
                "source_channel": "slack",
                "input_data": {},
            }
        )

    assert result["status"] == "no_agent"
    assert "couldn't find a suitable agent" in result["error"].lower()
    mock_reply.assert_called_once()


# ── Phase 3: BaseAgent Autonomous Methods ────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_user():
    """notify_user calls FeedbackManager.send_mention."""
    agent = MockAgent()
    with patch("angie.core.feedback.get_feedback") as mock_fb:
        mock_fb.return_value.send_mention = AsyncMock()
        await agent.notify_user("u1", "Hello!", channel="slack")
    mock_fb.return_value.send_mention.assert_called_once_with("u1", "Hello!", channel="slack")


@pytest.mark.asyncio
async def test_schedule_followup():
    """schedule_followup creates a ScheduledJob in the DB."""
    agent = MockAgent()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_factory = MagicMock(return_value=mock_session)

    with patch("angie.db.session.get_session_factory", return_value=mock_factory):
        job_id = await agent.schedule_followup(
            user_id="u1",
            delay_seconds=600,
            title="Check CI status",
            intent="Check CI for PR #42",
        )

    assert job_id  # Should return a UUID
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


# ── Phase 2.2: GitHub Agent Tools ────────────────────────────────────────────


def test_github_error_handler_rate_limit():
    """_handle_github_error returns actionable msg for rate limits."""
    import github as gh_module

    from angie.agents.dev.github import _handle_github_error

    exc = gh_module.RateLimitExceededException(403, {}, {})
    result = _handle_github_error(exc)
    assert "rate limit" in result["error"].lower()


def test_github_error_handler_bad_credentials():
    """_handle_github_error returns auth guidance for bad creds."""
    import github as gh_module

    from angie.agents.dev.github import _handle_github_error

    exc = gh_module.BadCredentialsException(401, {}, {})
    result = _handle_github_error(exc)
    assert "authentication" in result["error"].lower()


def test_github_error_handler_not_found():
    """_handle_github_error returns helpful msg for 404."""
    import github as gh_module

    from angie.agents.dev.github import _handle_github_error

    exc = gh_module.UnknownObjectException(404, {"message": "Not Found"}, {})
    result = _handle_github_error(exc)
    assert "not found" in result["error"].lower()


def test_github_error_handler_generic():
    """_handle_github_error handles generic exceptions."""
    from angie.agents.dev.github import _handle_github_error

    result = _handle_github_error(ValueError("test"))
    assert "Unexpected error" in result["error"]


def test_github_agent_has_new_tools():
    """GitHubAgent builds a pydantic agent with all expected tools."""
    from angie.agents.dev.github import GitHubAgent

    agent = GitHubAgent()
    pa = agent.build_pydantic_agent()
    tool_names = set(pa._function_toolset.tools.keys())

    expected_tools = {
        "list_repositories",
        "list_pull_requests",
        "list_issues",
        "create_issue",
        "get_repository",
        "comment_on_issue",
        "comment_on_pr",
        "merge_pull_request",
        "close_issue",
        "list_pr_checks",
        "get_pr_diff",
        "search_issues",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"


# ── Phase 2.3: SoftwareDev Agent Safety & Tools ─────────────────────────────


def test_softwaredev_branch_name_validation():
    """create_branch rejects invalid branch names."""
    from angie.agents.dev.software_dev import _BRANCH_NAME_PATTERN

    assert _BRANCH_NAME_PATTERN.match("angie/issue-42-fix-bug")
    assert _BRANCH_NAME_PATTERN.match("feature/add-tests")
    assert not _BRANCH_NAME_PATTERN.match("branch with spaces")
    assert not _BRANCH_NAME_PATTERN.match("branch;rm -rf /")


def test_softwaredev_file_size_limit():
    """write_file rejects files exceeding 100KB."""
    from angie.agents.dev.software_dev import _MAX_FILE_SIZE

    assert _MAX_FILE_SIZE == 100 * 1024


def test_softwaredev_workspace_size_limit():
    """Workspace size limit is 500MB."""
    from angie.agents.dev.software_dev import _MAX_WORKSPACE_SIZE

    assert _MAX_WORKSPACE_SIZE == 500 * 1024 * 1024


def test_softwaredev_agent_has_new_tools():
    """SoftwareDeveloperAgent builds an agent with all expected tools."""
    from angie.agents.dev.software_dev import SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()
    pa = agent.build_pydantic_agent()
    tool_names = set(pa._function_toolset.tools.keys())

    expected_tools = {
        "fetch_issue",
        "clone_repo",
        "create_branch",
        "read_file",
        "list_directory",
        "search_code",
        "write_file",
        "apply_patch",
        "run_tests",
        "check_ci_status",
        "run_command",
        "commit_and_push",
        "create_pull_request",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"


def test_softwaredev_get_dir_size():
    """_get_dir_size calculates directory size."""
    import tempfile

    from angie.agents.dev.software_dev import _get_dir_size

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "test.txt"
        p.write_text("hello world")
        size = _get_dir_size(Path(tmpdir))
        assert size > 0


# ── Phase 3.6: SoftwareDev CI Follow-up ─────────────────────────────────────


@pytest.mark.asyncio
async def test_softwaredev_schedule_ci_followup():
    """_schedule_ci_followup schedules follow-up when PR URL found."""
    from angie.agents.dev.software_dev import SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()

    with patch.object(agent, "schedule_followup", new_callable=AsyncMock) as mock_schedule:
        await agent._schedule_ci_followup(
            "Opened PR at https://github.com/owner/repo/pull/42",
            {"user_id": "u1"},
            "ghp_test",
        )

    mock_schedule.assert_called_once()
    call_kwargs = mock_schedule.call_args.kwargs
    assert call_kwargs["delay_seconds"] == 600
    assert "owner/repo" in call_kwargs["title"]
    assert call_kwargs["agent_slug"] == "software-dev"


@pytest.mark.asyncio
async def test_softwaredev_no_followup_without_pr_url():
    """_schedule_ci_followup does nothing when no PR URL in summary."""
    from angie.agents.dev.software_dev import SoftwareDeveloperAgent

    agent = SoftwareDeveloperAgent()

    with patch.object(agent, "schedule_followup", new_callable=AsyncMock) as mock_schedule:
        await agent._schedule_ci_followup(
            "I fixed the bug but didn't open a PR.",
            {"user_id": "u1"},
            "ghp_test",
        )

    mock_schedule.assert_not_called()


# ── Phase 2/Cleanup: Connections registry ────────────────────────────────────


def test_connections_registry_no_deleted_agents():
    """SERVICE_REGISTRY should not contain deleted agent services."""
    from angie.core.connections import SERVICE_REGISTRY

    deleted_services = {"spotify", "gmail", "gcal", "hue", "home_assistant", "unifi"}
    for service in deleted_services:
        assert service not in SERVICE_REGISTRY, f"Deleted service '{service}' still in registry"

    # Verify kept services are still present
    assert "github" in SERVICE_REGISTRY
    assert "slack" in SERVICE_REGISTRY
    assert "discord" in SERVICE_REGISTRY
    assert "openweathermap" in SERVICE_REGISTRY
