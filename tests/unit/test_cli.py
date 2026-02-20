"""Tests for angie.cli.* commands using Click's CliRunner."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── angie config tests ─────────────────────────────────────────────────────────


def test_config_slack(tmp_path):
    from angie.cli.config import config

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(config, ["slack"], input="xoxb-bot\nxapp-app\nsecret\n")
    assert result.exit_code == 0
    assert "Slack configured" in result.output


def test_config_discord(tmp_path):
    from angie.cli.config import config

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(config, ["discord"], input="discord-token\n")
    assert result.exit_code == 0
    assert "Discord configured" in result.output


def test_config_imessage(tmp_path):
    from angie.cli.config import config

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch("rich.prompt.Prompt.ask", side_effect=["https://bb.ngrok.io", "password123"]):
            result = runner.invoke(config, ["imessage"])
    assert result.exit_code == 0
    assert "iMessage configured" in result.output


def test_config_email(tmp_path):
    from angie.cli.config import config

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch(
            "rich.prompt.Prompt.ask",
            side_effect=[
                "smtp.gmail.com",
                "587",
                "imap.gmail.com",
                "993",
                "user@gmail.com",
                "app-pass",
            ],
        ):
            result = runner.invoke(config, ["email"])
    assert result.exit_code == 0
    assert "Email configured" in result.output


def test_config_channels(tmp_path):
    from angie.cli.config import config

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".env").write_text("SECRET_KEY=x\nDB_PASSWORD=x\nSLACK_BOT_TOKEN=xoxb-t\n")
        with patch("angie.config.get_settings") as mock_gs:
            s = MagicMock()
            s.slack_bot_token = "xoxb-test"
            s.discord_bot_token = None
            s.bluebubbles_url = None
            s.email_smtp_host = None
            s.email_imap_host = None
            mock_gs.return_value = s
            result = runner.invoke(config, ["channels"])
    assert result.exit_code == 0
    assert "Slack" in result.output


# ── angie ask tests ────────────────────────────────────────────────────────────


def test_ask_not_configured():
    from angie.cli.main import ask

    runner = CliRunner()
    with patch("angie.llm.is_llm_configured", return_value=False):
        result = runner.invoke(ask, ["hello"])
    assert result.exit_code == 1
    assert "No LLM configured" in result.output


def test_ask_success():
    from angie.cli.main import ask

    runner = CliRunner()

    with (
        patch("angie.llm.is_llm_configured", return_value=True),
        patch("asyncio.run", return_value="I am Angie, your assistant."),
    ):
        result = runner.invoke(ask, ["who am I?"])
    assert result.exit_code == 0


# ── angie status tests ─────────────────────────────────────────────────────────


def test_status_command():
    from angie.cli.status import status

    runner = CliRunner()
    mock_registry = MagicMock()
    mock_registry.list_all.return_value = []

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = runner.invoke(status)
    assert result.exit_code == 0


# ── angie prompts tests ────────────────────────────────────────────────────────


def test_prompts_list(tmp_path):
    from angie.cli.prompts import prompts

    runner = CliRunner()
    mock_pm = MagicMock()
    mock_pm.get_system_prompt.return_value = "# System\nYou are Angie."
    mock_pm.get_angie_prompt.return_value = "# Angie\nBe helpful."
    mock_pm.get_user_prompts.return_value = ["# Prefs\nShort answers."]

    with patch("angie.core.prompts.get_prompt_manager", return_value=mock_pm):
        result = runner.invoke(prompts, ["list"])
    assert result.exit_code == 0


# ── angie chat tests ───────────────────────────────────────────────────────────


def test_chat_not_configured():
    from angie.cli.chat import chat

    runner = CliRunner()
    # chat requires a positional MESSAGE argument, so with no args exit_code is 2
    result = runner.invoke(chat, [])
    assert result.exit_code == 2


def test_chat_session(tmp_path):
    from angie.cli.chat import chat

    runner = CliRunner()
    mock_registry = MagicMock()
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value={"response": "Hi there!"})
    mock_registry.resolve.return_value = mock_agent

    with patch("angie.agents.registry.get_registry", return_value=mock_registry):
        result = runner.invoke(chat, ["hello", "world"])
    assert result.exit_code == 0
