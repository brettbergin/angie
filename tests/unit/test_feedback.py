"""Tests for angie.core.feedback (FeedbackManager)."""

from unittest.mock import AsyncMock, MagicMock, patch


async def test_send_success():
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_success("user1", "All done", channel="slack", task_id="t1")

    mock_channel_mgr.send.assert_called_once()
    call_kwargs = mock_channel_mgr.send.call_args.kwargs
    assert call_kwargs["user_id"] == "user1"
    assert "✅ All done" in call_kwargs["text"]
    assert call_kwargs["channel_type"] == "slack"


async def test_send_failure_no_error():
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_failure("user1", "Something failed", channel="discord")

    mock_channel_mgr.send.assert_called_once()
    text = mock_channel_mgr.send.call_args.kwargs["text"]
    assert "❌ Something failed" in text


async def test_send_failure_with_error():
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_failure("user1", "Job failed", error="Traceback...", channel="slack")

    text = mock_channel_mgr.send.call_args.kwargs["text"]
    assert "❌ Job failed" in text
    assert "Traceback..." in text


async def test_send_mention():
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr.send_mention("user1", "Check this out", channel="slack")

    text = mock_channel_mgr.send.call_args.kwargs["text"]
    assert "user1" in text
    assert "Check this out" in text


async def test_send_no_channel():
    from angie.core.feedback import FeedbackManager

    mgr = FeedbackManager()
    mock_channel_mgr = MagicMock()
    mock_channel_mgr.send = AsyncMock()

    with patch("angie.channels.base.get_channel_manager", return_value=mock_channel_mgr):
        await mgr._send("user1", "Hello", None)

    mock_channel_mgr.send.assert_called_once_with(
        user_id="user1", text="Hello", channel_type=None
    )


def test_get_feedback_singleton():
    import angie.core.feedback as fb_mod

    fb_mod._feedback = None
    mgr1 = fb_mod.get_feedback()
    mgr2 = fb_mod.get_feedback()
    assert mgr1 is mgr2
    fb_mod._feedback = None
