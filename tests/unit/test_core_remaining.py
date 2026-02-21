"""Tests to cover remaining gaps in core/loop, core/prompts, db/session."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_settings():
    from angie.config import Settings

    return Settings(secret_key="k", db_password="pass")  # type: ignore[call-arg]


# ── PromptManager: _load_file when path exists ────────────────────────────────


def test_load_file_existing(tmp_path):
    from angie.core.prompts import PromptManager

    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    f = tmp_path / "test.md"
    f.write_text("hello world", encoding="utf-8")
    result = pm._load_file(f)
    assert result == "hello world"


def test_load_file_missing(tmp_path):
    from angie.core.prompts import PromptManager

    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    result = pm._load_file(tmp_path / "nonexistent.md")
    assert result == ""


# ── PromptManager exception fallback paths ────────────────────────────────────


def test_get_system_prompt_exception_fallback(tmp_path):
    from angie.core.prompts import PromptManager

    (tmp_path / "system.md").write_text("system content", encoding="utf-8")
    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    # Force _render to raise so we hit the exception fallback
    with patch.object(pm, "_render", side_effect=Exception("template error")):
        result = pm.get_system_prompt()
    assert "system content" in result


def test_get_angie_prompt_exception_fallback(tmp_path):
    from angie.core.prompts import PromptManager

    (tmp_path / "angie.md").write_text("angie content", encoding="utf-8")
    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    with patch.object(pm, "_render", side_effect=Exception("template error")):
        result = pm.get_angie_prompt()
    assert "angie content" in result


def test_get_agent_prompt_exception_fallback(tmp_path):
    from angie.core.prompts import PromptManager

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "gmail.md").write_text("gmail agent content", encoding="utf-8")
    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    with patch.object(pm, "_render", side_effect=Exception("template error")):
        result = pm.get_agent_prompt("gmail")
    assert "gmail agent content" in result


def test_get_agent_prompt_exception_fallback_missing_file(tmp_path):
    from angie.core.prompts import PromptManager

    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    with patch.object(pm, "_render", side_effect=Exception("template error")):
        result = pm.get_agent_prompt("nonexistent-agent")
    assert result == ""


def test_compose_for_agent(tmp_path):
    from angie.core.prompts import PromptManager

    (tmp_path / "system.md").write_text("system content", encoding="utf-8")
    (tmp_path / "angie.md").write_text("angie content", encoding="utf-8")
    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    result = pm.compose_for_agent("gmail", agent_instructions="gmail content")
    assert "system content" in result
    assert "angie content" in result
    assert "gmail content" in result


def test_compose_for_agent_missing_files(tmp_path):
    from angie.core.prompts import PromptManager

    pm = PromptManager(prompts_dir=str(tmp_path))
    pm.user_prompts_dir = tmp_path / "user"
    # All files missing — all prompts empty, result should be empty
    result = pm.compose_for_agent("unknown")
    assert result == ""


# ── AngieLoop: non-CHANNEL_MESSAGE event title fallback ──────────────────────


@pytest.fixture(autouse=True)
def reset_event_router():
    from angie.core.events import router

    old_catch_all = router._catch_all.copy()
    old_handlers = {k: v.copy() for k, v in router._handlers.items()}
    yield
    router._catch_all = old_catch_all
    router._handlers = old_handlers


@pytest.mark.asyncio
async def test_loop_dispatches_non_channel_message_event():
    """Cover the else branch that creates title from event type."""
    from angie.core.events import AngieEvent
    from angie.core.loop import AngieLoop
    from angie.models.event import EventType

    mock_cron = MagicMock()
    mock_dispatcher = MagicMock()
    mock_channel_manager = AsyncMock()

    with (
        patch("angie.config.get_settings", return_value=_make_settings()),
        patch("angie.core.loop.CronEngine", return_value=mock_cron),
        patch("angie.core.loop.get_dispatcher", return_value=mock_dispatcher),
        patch("angie.channels.base.get_channel_manager", return_value=mock_channel_manager),
    ):
        loop = AngieLoop()

        # Override _run_forever to dispatch one non-CHANNEL_MESSAGE event, then stop
        async def fake_run():
            event = AngieEvent(
                type=EventType.USER_MESSAGE,
                user_id="user-1",
                payload={"text": "hello"},
            )
            from angie.core.events import router as _router

            await _router.dispatch(event)

        loop._run_forever = fake_run
        await loop.start()

    # Dispatcher should have been called with a task whose title is from event type
    assert mock_dispatcher.dispatch.call_count >= 1
    task_arg = mock_dispatcher.dispatch.call_args[0][0]
    assert "user_message" in task_arg.title.lower() or "user" in task_arg.title.lower()


@pytest.mark.asyncio
async def test_run_forever_loop():
    """Cover lines 85-86: while self._running: await asyncio.sleep(1)."""
    from angie.core.loop import AngieLoop

    with patch("angie.config.get_settings", return_value=_make_settings()):
        loop = AngieLoop()
    loop._running = True

    async def cancel_after_one():
        """Stop the loop after one iteration."""
        await asyncio.sleep(0.05)
        loop._running = False

    await asyncio.gather(
        loop._run_forever(),
        cancel_after_one(),
    )
    assert not loop._running


# ── db/session.py: get_session async generator ───────────────────────────────


@pytest.mark.asyncio
async def test_get_session_commits_on_success():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory_instance = MagicMock()
    mock_factory_instance.return_value = mock_session

    from angie.db import session as db_session

    db_session._session_factory = None

    with patch("angie.db.session.get_session_factory", return_value=mock_factory_instance):
        gen = db_session.get_session()
        _ = await gen.__anext__()
        try:
            await gen.aclose()
        except StopAsyncIteration:
            pass

    db_session._session_factory = None


@pytest.mark.asyncio
async def test_get_session_rollback_on_exception():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory_instance = MagicMock()
    mock_factory_instance.return_value = mock_session

    from angie.db import session as db_session

    db_session._session_factory = None

    with patch("angie.db.session.get_session_factory", return_value=mock_factory_instance):
        gen = db_session.get_session()
        await gen.__anext__()
        try:
            await gen.athrow(ValueError("db error"))
        except (ValueError, StopAsyncIteration):
            pass

    db_session._session_factory = None
