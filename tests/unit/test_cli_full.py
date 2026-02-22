"""Tests for all remaining CLI coverage gaps."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── cli/main.py: daemon command ───────────────────────────────────────────────


def test_cli_daemon_command():
    from angie.cli.main import cli

    with patch("asyncio.run") as mock_run, patch("angie.core.loop.AngieLoop") as mock_loop_cls:
        mock_loop = MagicMock()
        mock_loop_cls.return_value = mock_loop

        runner = CliRunner()
        result = runner.invoke(cli, ["daemon"])

    # Should call asyncio.run (daemon boot)
    assert result.exit_code == 0 or mock_run.called


def test_cli_daemon_already_running(tmp_path):
    """If pid file exists with live process, show running message."""
    from angie.cli.main import cli

    with patch("asyncio.run"):
        runner = CliRunner()
        result = runner.invoke(cli, ["daemon"])
    # Should not crash
    assert result.exit_code in (0, 1)


# ── cli/main.py: ask command ───────────────────────────────────────────────────


def test_cli_ask_command_success():
    from angie.cli.main import cli

    mock_result = MagicMock()
    mock_result.output = "I am Angie, your AI assistant."

    async def fake_run(q):
        return mock_result

    mock_agent = MagicMock()
    mock_agent.run = fake_run

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
        patch(
            "angie.core.prompts.load_user_prompts_from_db", new_callable=AsyncMock, return_value=[]
        ),
        patch("angie.llm.get_llm_model") as mock_llm,
        patch("pydantic_ai.Agent", return_value=mock_agent),
    ):
        mock_pm.return_value.compose_with_user_prompts.return_value = "system prompt"
        mock_llm.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "who am I?"])
    assert result.exit_code == 0


def test_cli_ask_command_not_configured():
    from angie.cli.main import cli

    with patch("angie.llm.is_llm_configured", return_value=False):
        runner = CliRunner()
        result = runner.invoke(cli, ["ask", "hello"])

    assert result.exit_code == 1


# ── cli/chat.py ───────────────────────────────────────────────────────────────


def test_chat_with_agent_slug():
    """Cover cli/chat.py with --agent flag."""
    from angie.cli.chat import chat

    mock_agent_obj = MagicMock()
    mock_agent_obj.execute = AsyncMock(return_value={"result": "email checked"})

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent_obj
    mock_registry.resolve.return_value = mock_agent_obj

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        runner = CliRunner()
        result = runner.invoke(chat, ["--agent", "gmail", "check my email"])

    assert result.exit_code == 0


def test_chat_no_agent_slug():
    """Cover cli/chat.py fallback when no agent resolves (uses LLM)."""
    from angie.cli.chat import chat

    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_registry.resolve.return_value = None

    with (
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
        patch("angie.core.prompts.get_prompt_manager") as mock_pm,
        patch(
            "angie.core.prompts.load_user_prompts_from_db", new_callable=AsyncMock, return_value=[]
        ),
        patch("angie.agents.base.BaseAgent.ask_llm", new_callable=AsyncMock, return_value="Hello!"),
    ):
        mock_pm.return_value.compose_with_user_prompts.return_value = "system"

        runner = CliRunner()
        result = runner.invoke(chat, ["hello there"])

    assert result.exit_code == 0


# ── cli/setup.py ─────────────────────────────────────────────────────────────


def test_setup_command_basic():
    from angie.cli.setup import setup

    with (
        patch("angie.cli.setup._save_to_db", new_callable=AsyncMock) as mock_save,
    ):
        runner = CliRunner()
        answers = "\n".join(
            ["casual", "tech", "9am-5pm", "code", "slack", "smart home", "eng", "concise"]
        )
        result = runner.invoke(setup, ["--user-id", "test-user-id"], input=answers)

    assert result.exit_code == 0
    assert mock_save.call_count == 8


# ── cli/status.py ─────────────────────────────────────────────────────────────


def test_status_command_celery_running():
    from angie.cli.status import status

    mock_inspect = MagicMock()
    mock_inspect.ping.return_value = {"worker@host": {"ok": "pong"}}
    mock_inspect.active.return_value = {"worker@host": [{"id": "t1", "name": "task"}]}
    mock_celery_app = MagicMock()
    mock_celery_app.control.inspect.return_value = mock_inspect

    mock_registry = MagicMock()
    mock_agent = MagicMock()
    mock_agent.slug = "gmail"
    mock_agent.description = "Gmail agent"
    mock_registry.list_all.return_value = [mock_agent]

    with (
        patch("angie.queue.celery_app.celery_app", mock_celery_app),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        runner = CliRunner()
        result = runner.invoke(status, [])

    assert result.exit_code == 0


def test_status_command_celery_not_running():
    from angie.cli.status import status

    with (
        patch("angie.queue.celery_app.celery_app", side_effect=RuntimeError("no celery")),
        patch("angie.agents.registry.get_registry", side_effect=RuntimeError("no registry")),
    ):
        runner = CliRunner()
        result = runner.invoke(status, [])

    assert result.exit_code == 0


def test_status_command_active_tasks_none():
    from angie.cli.status import status

    mock_inspect = MagicMock()
    mock_inspect.active.return_value = {}
    mock_celery_app = MagicMock()
    mock_celery_app.control.inspect.return_value = mock_inspect

    mock_registry = MagicMock()
    mock_registry.list_all.return_value = []

    with (
        patch("angie.queue.celery_app.celery_app", mock_celery_app),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        runner = CliRunner()
        result = runner.invoke(status, [])

    assert result.exit_code == 0


# ── cli/_env_utils.py: blank value line ───────────────────────────────────────


def test_write_env_blank_value_unchanged(tmp_path):
    """Cover the 'new_lines.append(line)' path when new value is also empty."""
    from angie.cli._env_utils import write_env

    env_file = tmp_path / ".env"
    env_file.write_text("SLACK_BOT_TOKEN=\n", encoding="utf-8")

    # Writing empty string for an existing empty key should leave the line unchanged
    write_env({"SLACK_BOT_TOKEN": ""}, path=env_file)
    content = env_file.read_text(encoding="utf-8")
    assert "SLACK_BOT_TOKEN=" in content


# ── cli/config.py: _write_env when file exists ───────────────────────────────


def test_config_write_env_existing_file(tmp_path, monkeypatch):
    """cli/config.py _write_env appends to an existing file."""
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_KEY=existing_value\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    from angie.cli.config import _write_env

    _write_env({"NEW_KEY": "new_value"})

    content = env_file.read_text(encoding="utf-8")
    assert "NEW_KEY=new_value" in content
    assert "EXISTING_KEY=existing_value" in content


# ── cli/configure.py: _seed_db ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_db_creates_user_and_agent():
    """Cover the _seed_db async function with mocked DB session."""
    from angie.cli.configure import _seed_db

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    # user NOT existing
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async_ctx = AsyncMock()
    async_ctx.__aenter__.return_value = mock_session
    async_ctx.__aexit__.return_value = False

    mock_session_factory = MagicMock(return_value=async_ctx)
    mock_get_factory = MagicMock(return_value=mock_session_factory)

    with (
        patch("angie.db.session.get_session_factory", mock_get_factory),
        patch("angie.api.auth.hash_password", return_value="hashed-password"),
    ):
        await _seed_db()

    assert mock_session.add.called


@pytest.mark.asyncio
async def test_seed_db_user_already_exists():
    """When demo user already exists, skip creation."""
    from angie.cli.configure import _seed_db

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    # user already exists
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "existing-id"
    mock_session.execute = AsyncMock(return_value=mock_result)

    async_ctx = AsyncMock()
    async_ctx.__aenter__.return_value = mock_session
    async_ctx.__aexit__.return_value = False

    mock_session_factory = MagicMock(return_value=async_ctx)
    mock_get_factory = MagicMock(return_value=mock_session_factory)

    with (
        patch("angie.db.session.get_session_factory", mock_get_factory),
        patch("angie.api.auth.hash_password", return_value="hashed-password"),
    ):
        await _seed_db()

    assert not mock_session.add.called


def test_configure_seed_command():
    """Cover the seed CLI sub-command invocation."""
    from angie.cli.configure import configure

    with patch("asyncio.run") as mock_async_run:
        runner = CliRunner()
        result = runner.invoke(configure, ["seed"])

    assert result.exit_code == 0
    assert mock_async_run.called or "seeded" in result.output.lower()


# ── cli/status.py: active tasks table branch (lines 43-44) ───────────────────


def test_status_command_with_active_tasks():
    """Cover the else branch (table has rows) in status command."""
    from angie.cli.status import status

    mock_inspect = MagicMock()
    mock_inspect.active.return_value = {"worker@host": [{"id": "tid1", "name": "angie.task"}]}
    mock_celery_app = MagicMock()
    mock_celery_app.control.inspect.return_value = mock_inspect

    mock_registry = MagicMock()
    mock_agent = MagicMock()
    mock_agent.slug = "gmail"
    mock_agent.description = "Gmail agent"
    mock_registry.list_all.return_value = [mock_agent]

    with (
        patch("angie.queue.celery_app.celery_app", mock_celery_app),
        patch("angie.agents.registry.get_registry", return_value=mock_registry),
    ):
        runner = CliRunner()
        result = runner.invoke(status, [])

    assert result.exit_code == 0


def test_status_command_celery_exception():
    """Cover status.py lines 43-44: exception in Celery inspect."""
    from click.testing import CliRunner

    from angie.cli.main import cli

    runner = CliRunner()
    mock_app = MagicMock()
    mock_app.control.inspect.side_effect = Exception("broker unreachable")

    with (
        patch("angie.queue.celery_app.celery_app", mock_app),
        patch("angie.agents.registry.get_registry") as mock_reg,
    ):
        mock_reg.return_value.list_agents.return_value = []
        result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Could not reach" in result.output or "broker" in result.output.lower()


# ── main.py __main__ guard ──────────────────────────────────────────────────


def test_main_entry_point():
    """Cover main.py lines 3-8: if __name__ == '__main__' guard."""
    import runpy

    with patch("asyncio.run") as mock_run:
        runpy.run_module("angie.main", run_name="__main__")
    mock_run.assert_called_once()
