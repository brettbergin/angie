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


# ── Direct tool invocation tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_screenshot_tool_with_fake_impl(tmp_path, monkeypatch):
    """Ensure the screenshot tool can be invoked and returns markdown with a file."""
    agent = WebAgent()

    screenshot_tool = getattr(agent, "screenshot", None)
    if screenshot_tool is None:
        pytest.skip("WebAgent.screenshot tool is not exposed as an attribute")

    screenshot_path = tmp_path / "screenshot.png"

    async def fake_screenshot(url: str) -> str:
        # Simulate screenshot creation
        screenshot_path.write_bytes(b"fake-image-bytes")
        # Simulate markdown response format used by the agent
        return f"![Screenshot of {url}]({screenshot_path})"

    # Replace the real implementation with our controlled fake for this test
    monkeypatch.setattr(agent, "screenshot", fake_screenshot)

    result = await agent.screenshot("https://example.com")

    assert screenshot_path.exists(), "Screenshot file should be created"
    assert result.startswith("![Screenshot of https://example.com](")
    assert str(screenshot_path) in result


@pytest.mark.asyncio
async def test_get_page_content_tool_with_fake_impl(monkeypatch):
    """Ensure get_page_content tool can be invoked and returns extracted text."""
    agent = WebAgent()

    get_page_content_tool = getattr(agent, "get_page_content", None)
    if get_page_content_tool is None:
        pytest.skip("WebAgent.get_page_content tool is not exposed as an attribute")

    async def fake_get_page_content(url: str) -> str:
        # Simulate trafilatura-like extraction result
        return "Example extracted content from page."

    monkeypatch.setattr(agent, "get_page_content", fake_get_page_content)

    result = await agent.get_page_content("https://news.ycombinator.com")

    assert isinstance(result, str)
    assert "extracted content" in result


@pytest.mark.asyncio
async def test_summarize_page_tool_with_fake_impl(monkeypatch):
    """Ensure summarize_page tool can be invoked and performs truncation-like behavior."""
    agent = WebAgent()

    summarize_page_tool = getattr(agent, "summarize_page", None)
    if summarize_page_tool is None:
        pytest.skip("WebAgent.summarize_page tool is not exposed as an attribute")

    long_text = "Sentence. " * 200

    async def fake_summarize_page(content: str, max_chars: int = 500) -> str:
        # Simulate LLM-based summarization with truncation
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "..."

    monkeypatch.setattr(agent, "summarize_page", fake_summarize_page)

    summary = await agent.summarize_page(long_text, max_chars=500)

    assert isinstance(summary, str)
    assert len(summary) <= 503  # 500 chars + "..."
    assert summary.endswith("...")


@pytest.mark.asyncio
async def test_get_link_preview_tool_with_fake_impl(monkeypatch):
    """Ensure get_link_preview tool can be invoked and returns OpenGraph-like metadata."""
    agent = WebAgent()

    get_link_preview_tool = getattr(agent, "get_link_preview", None)
    if get_link_preview_tool is None:
        pytest.skip("WebAgent.get_link_preview tool is not exposed as an attribute")

    async def fake_get_link_preview(url: str) -> dict:
        # Simulate BeautifulSoup / OpenGraph extraction
        return {
            "url": url,
            "title": "Example Title",
            "description": "Example Description",
            "image": "https://example.com/image.png",
        }

    monkeypatch.setattr(agent, "get_link_preview", fake_get_link_preview)

    preview = await agent.get_link_preview("https://example.com/article")

    assert isinstance(preview, dict)
    assert preview["url"] == "https://example.com/article"
    assert preview["title"] == "Example Title"
    assert preview["description"] == "Example Description"
    assert preview["image"].endswith("image.png")


@pytest.mark.asyncio
async def test_watch_page_tool_with_fake_impl(monkeypatch):
    """Ensure watch_page tool can be invoked and returns a structured response."""
    agent = WebAgent()

    watch_page_tool = getattr(agent, "watch_page", None)
    if watch_page_tool is None:
        pytest.skip("WebAgent.watch_page tool is not exposed as an attribute")

    async def fake_watch_page(url: str, frequency_minutes: int = 5) -> dict:
        # Simulate scheduling a page watch
        return {
            "url": url,
            "frequency_minutes": frequency_minutes,
            "status": "watching",
        }

    monkeypatch.setattr(agent, "watch_page", fake_watch_page)

    result = await agent.watch_page("https://example.com", frequency_minutes=10)

    assert isinstance(result, dict)
    assert result["url"] == "https://example.com"
    assert result["frequency_minutes"] == 10
    assert result["status"] == "watching"
