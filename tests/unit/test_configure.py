"""Tests for angie.cli.configure and angie.cli._env_utils."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")


# ── _env_utils tests ───────────────────────────────────────────────────────────

def test_read_env_empty(tmp_path):
    from angie.cli._env_utils import read_env
    assert read_env(tmp_path / "missing.env") == {}


def test_read_env_parses_values(tmp_path):
    from angie.cli._env_utils import read_env
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=qux\n# comment\nEMPTY=\n")
    result = read_env(env_file)
    assert result["FOO"] == "bar"
    assert result["BAZ"] == "qux"
    assert result["EMPTY"] == ""


def test_write_env_creates_file(tmp_path):
    from angie.cli._env_utils import write_env
    env_file = tmp_path / ".env"
    write_env({"KEY1": "val1"}, env_file)
    assert "KEY1=val1" in env_file.read_text()


def test_write_env_updates_existing(tmp_path):
    from angie.cli._env_utils import read_env, write_env
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=old\nKEY2=keep\n")
    write_env({"KEY1": "new"}, env_file)
    result = read_env(env_file)
    assert result["KEY1"] == "new"
    assert result["KEY2"] == "keep"


def test_write_env_appends_new_keys(tmp_path):
    from angie.cli._env_utils import read_env, write_env
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=val1\n")
    write_env({"KEY2": "val2"}, env_file)
    result = read_env(env_file)
    assert result["KEY1"] == "val1"
    assert result["KEY2"] == "val2"


def test_write_env_skips_empty_values(tmp_path):
    from angie.cli._env_utils import write_env
    env_file = tmp_path / ".env"
    write_env({"EMPTY": ""}, env_file)
    content = env_file.read_text()
    assert "EMPTY" not in content


def test_mask_none():
    from angie.cli._env_utils import mask
    assert mask(None) == ""


def test_mask_short():
    from angie.cli._env_utils import mask
    assert mask("abc") == "***"


def test_mask_long():
    from angie.cli._env_utils import mask
    result = mask("ghp_abcdefghij")
    assert result.startswith("ghp_")
    assert "****" in result


# ── configure keys tests ───────────────────────────────────────────────────────

def test_configure_keys_slack(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            configure,
            ["keys", "slack"],
            input="xoxb-test-token\nxapp-test-token\nsigning-secret-123\n",
        )
    assert result.exit_code == 0
    assert "SLACK" in result.output or "configured" in result.output.lower()


def test_configure_keys_discord(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            configure,
            ["keys", "discord"],
            input="discord-bot-token-123\n",
        )
    assert result.exit_code == 0


def test_configure_keys_llm(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            configure,
            ["keys", "llm"],
            input="ghp_testtoken\n\nhttps://api.githubcopilot.com\n",
        )
    assert result.exit_code == 0


def test_configure_keys_no_changes(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # All empty inputs → no changes
        result = runner.invoke(
            configure,
            ["keys", "discord"],
            input="\n",
        )
    assert result.exit_code == 0


def test_configure_keys_invalid_service():
    from angie.cli.configure import configure

    runner = CliRunner()
    result = runner.invoke(configure, ["keys", "nonexistent"])
    assert result.exit_code != 0


# ── configure list tests ───────────────────────────────────────────────────────

def test_configure_list(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".env").write_text("GITHUB_TOKEN=ghp_abc123\nSLACK_BOT_TOKEN=xoxb-test\n")
        result = runner.invoke(configure, ["list"])
    assert result.exit_code == 0
    assert "GITHUB_TOKEN" in result.output
    assert "SLACK_BOT_TOKEN" in result.output


def test_configure_list_empty(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(configure, ["list"])
    assert result.exit_code == 0
    assert "not set" in result.output


# ── configure model tests ──────────────────────────────────────────────────────

def test_configure_model_select(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Pick gpt-4o-mini, keep default base URL
        result = runner.invoke(
            configure,
            ["model"],
            input="gpt-4o-mini\nhttps://api.githubcopilot.com\n",
        )
    assert result.exit_code == 0
    assert "gpt-4o-mini" in result.output


def test_configure_model_default(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".env").write_text("COPILOT_MODEL=gpt-4o\n")
        # Press enter to keep defaults
        result = runner.invoke(configure, ["model"], input="\n\n")
    assert result.exit_code == 0


# ── configure seed tests ───────────────────────────────────────────────────────

def test_configure_seed_success(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with patch("angie.cli.configure._seed_db", new_callable=AsyncMock) as mock_seed:
        result = runner.invoke(configure, ["seed"])
    assert result.exit_code == 0
    mock_seed.assert_called_once()


def test_configure_seed_db_error(tmp_path):
    from angie.cli.configure import configure

    runner = CliRunner()
    with patch(
        "angie.cli.configure._seed_db",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB unreachable"),
    ):
        result = runner.invoke(configure, ["seed"])
    assert result.exit_code == 1
    assert "Seed failed" in result.output or "DB unreachable" in result.output
