"""Tests for _extract_mention and _extract_mentions in chat router."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("DB_PASSWORD", "test-password")


def _make_mock_registry(slugs: list[str]):
    """Create a mock agent registry with the given slugs."""
    agents = []
    for slug in slugs:
        a = MagicMock()
        a.slug = slug
        agents.append(a)
    registry = MagicMock()
    registry.list_all.return_value = agents
    return registry


@patch("angie.config.get_settings")
def test_extract_mention_valid_agent(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify", "gmail", "hue"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("@spotify what's playing?")
        assert slug == "spotify"
        assert kind == "agent"
        assert cleaned == "what's playing?"


@patch("angie.config.get_settings")
def test_extract_mention_valid_team(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify", "gmail"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention(
            "@media-team do something", team_slugs={"media-team"}
        )
        assert slug == "media-team"
        assert kind == "team"
        assert cleaned == "do something"


@patch("angie.config.get_settings")
def test_extract_mention_invalid_slug(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify", "gmail"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("@nonexistent hello")
        assert slug is None
        assert kind is None
        assert cleaned == "@nonexistent hello"


@patch("angie.config.get_settings")
def test_extract_mention_no_mention(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("just a normal message")
        assert slug is None
        assert kind is None
        assert cleaned == "just a normal message"


@patch("angie.config.get_settings")
def test_extract_mention_middle_of_message(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("hey @spotify play jazz")
        assert slug == "spotify"
        assert kind == "agent"
        assert cleaned == "hey  play jazz"


@patch("angie.config.get_settings")
def test_extract_mention_case_insensitive(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("@Spotify play jazz")
        assert slug == "spotify"
        assert kind == "agent"


@patch("angie.config.get_settings")
def test_extract_mention_at_end(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["spotify"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("play jazz @spotify")
        assert slug == "spotify"
        assert kind == "agent"
        assert cleaned == "play jazz"


@patch("angie.config.get_settings")
def test_extract_mention_ignores_email(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["gmail", "spotify"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mention

        slug, kind, cleaned = _extract_mention("send to user@gmail.com")
        assert slug is None
        assert kind is None
        assert cleaned == "send to user@gmail.com"


# ── _extract_mentions (plural) tests ──────────────────────────────────────────


@patch("angie.config.get_settings")
def test_extract_mentions_two_agents(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["weather", "github"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mentions

        mentions, cleaned = _extract_mentions("@weather forecast for NYC @github check my PRs")
        assert mentions == [("weather", "agent"), ("github", "agent")]
        assert "forecast for NYC" in cleaned
        assert "check my PRs" in cleaned
        assert "@weather" not in cleaned
        assert "@github" not in cleaned


@patch("angie.config.get_settings")
def test_extract_mentions_agent_and_team(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["weather"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mentions

        mentions, cleaned = _extract_mentions(
            "@weather forecast @media-team play music", team_slugs={"media-team"}
        )
        assert mentions == [("weather", "agent"), ("media-team", "team")]
        assert "@weather" not in cleaned
        assert "@media-team" not in cleaned


@patch("angie.config.get_settings")
def test_extract_mentions_dedup(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["weather"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mentions

        mentions, cleaned = _extract_mentions("@weather in NYC @weather in LA")
        assert mentions == [("weather", "agent")]
        assert "@weather" not in cleaned


@patch("angie.config.get_settings")
def test_extract_mentions_no_mentions(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["weather"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mentions

        mentions, cleaned = _extract_mentions("just a normal message")
        assert mentions == []
        assert cleaned == "just a normal message"


@patch("angie.config.get_settings")
def test_extract_mentions_invalid_slugs_ignored(mock_gs):
    mock_gs.return_value = MagicMock()
    registry = _make_mock_registry(["weather"])
    with patch("angie.agents.registry.get_registry", return_value=registry):
        from angie.api.routers.chat import _extract_mentions

        mentions, cleaned = _extract_mentions("@nonexistent hello @weather forecast")
        assert mentions == [("weather", "agent")]
        assert "@nonexistent" in cleaned  # invalid slug stays in message
        assert "@weather" not in cleaned
