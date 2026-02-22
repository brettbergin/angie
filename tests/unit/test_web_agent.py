"""Unit tests for the Web/Screenshot agent."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DB_PASSWORD", "test-password")

from angie.agents.productivity.web import WebAgent, _is_private_ip, _validate_url

# ── ClassVars ──────────────────────────────────────────────────────────────────


def test_web_agent_classvars():
    agent = WebAgent()
    assert agent.slug == "web"
    assert agent.name == "Web Agent"
    assert agent.category == "Productivity"
    assert "screenshot" in agent.capabilities
    assert "browse" in agent.capabilities
    assert "summarize" in agent.capabilities


def test_web_agent_description():
    agent = WebAgent()
    assert agent.description
    assert len(agent.description) > 10


# ── URL Validation / SSRF ─────────────────────────────────────────────────────


def test_validate_url_valid_http():
    with patch("angie.agents.productivity.web._is_private_ip", return_value=False):
        result = _validate_url("https://example.com")
    assert result == "https://example.com"


def test_validate_url_valid_http_with_path():
    with patch("angie.agents.productivity.web._is_private_ip", return_value=False):
        result = _validate_url("https://example.com/page?q=test")
    assert result == "https://example.com/page?q=test"


def test_validate_url_blocks_ftp():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _validate_url("ftp://example.com/file")


def test_validate_url_blocks_file():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _validate_url("file:///etc/passwd")


def test_validate_url_blocks_javascript():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _validate_url("javascript:alert(1)")


def test_validate_url_blocks_empty_scheme():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        _validate_url("://example.com")


def test_validate_url_blocks_no_hostname():
    with pytest.raises(ValueError, match="no hostname"):
        _validate_url("http://")


def test_validate_url_blocks_private_ip():
    with patch("angie.agents.productivity.web._is_private_ip", return_value=True):
        with pytest.raises(ValueError, match="private/internal"):
            _validate_url("http://192.168.1.1")


def test_is_private_ip_localhost():
    assert _is_private_ip("127.0.0.1") is True


def test_is_private_ip_unresolvable():
    assert _is_private_ip("this-host-does-not-exist.invalid") is True


def test_is_private_ip_public():
    with patch(
        "socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("93.184.216.34", 0)),
        ],
    ):
        assert _is_private_ip("example.com") is False


def test_is_private_ip_ten_range():
    with patch(
        "socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("10.0.0.1", 0)),
        ],
    ):
        assert _is_private_ip("internal.example.com") is True


def test_is_private_ip_link_local():
    with patch(
        "socket.getaddrinfo",
        return_value=[
            (2, 1, 6, "", ("169.254.1.1", 0)),
        ],
    ):
        assert _is_private_ip("link-local.example.com") is True


# ── can_handle ─────────────────────────────────────────────────────────────────


def test_can_handle_by_slug():
    agent = WebAgent()
    assert agent.can_handle({"agent_slug": "web"}) is True
    assert agent.can_handle({"agent_slug": "github"}) is False


def test_can_handle_by_capability():
    agent = WebAgent()
    assert agent.can_handle({"title": "take a screenshot of example.com"}) is True
    assert agent.can_handle({"title": "browse to google.com"}) is True
    assert agent.can_handle({"title": "summarize this page"}) is True


def test_can_handle_no_match():
    agent = WebAgent()
    assert agent.can_handle({"title": "send an email"}) is False


# ── execute ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_success():
    agent = WebAgent()
    mock_result = MagicMock(output="Screenshot taken successfully.")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(agent, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await agent.execute(
            {
                "title": "screenshot https://example.com",
                "input_data": {"intent": "take a screenshot of https://example.com"},
            }
        )
    assert result["summary"] == "Screenshot taken successfully."
    assert "error" not in result


@pytest.mark.asyncio
async def test_execute_error():
    agent = WebAgent()
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    with (
        patch.object(agent, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        result = await agent.execute(
            {
                "title": "screenshot https://example.com",
                "input_data": {},
            }
        )
    assert "error" in result
    assert "LLM unavailable" in result["error"]


@pytest.mark.asyncio
async def test_execute_extracts_intent():
    agent = WebAgent()
    mock_result = MagicMock(output="Done.")
    mock_pai = MagicMock()
    mock_pai.run = AsyncMock(return_value=mock_result)
    with (
        patch.object(agent, "_get_agent", return_value=mock_pai),
        patch("angie.llm.get_llm_model", return_value=MagicMock()),
    ):
        await agent.execute(
            {
                "title": "get content",
                "input_data": {"intent": "extract content from https://news.ycombinator.com"},
            }
        )
    call_args = mock_pai.run.call_args
    assert "extract content" in call_args[0][0]


# ── Link preview parsing ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_link_preview_parsing():
    """Test that get_link_preview tool is registered."""
    from angie.agents.productivity.web import WebAgent

    agent = WebAgent()
    pydantic_agent = agent.build_pydantic_agent()

    tool_names = list(pydantic_agent._function_toolset.tools.keys())
    assert "get_link_preview" in tool_names


def test_build_pydantic_agent_registers_tools():
    """Verify all expected tools are registered."""
    agent = WebAgent()
    pydantic_agent = agent.build_pydantic_agent()
    tool_names = set(pydantic_agent._function_toolset.tools.keys())
    expected = {
        "screenshot",
        "get_page_content",
        "summarize_page",
        "get_link_preview",
        "watch_page",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"
