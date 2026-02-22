"""Web/Screenshot agent — browse URLs, take screenshots, extract and summarize page content."""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

import httpx
from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


def _is_private_ip(host: str) -> bool:
    """Return True if *host* resolves to a private/reserved IP address."""
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                return True
    except (socket.gaierror, ValueError):
        return True  # unresolvable → block
    return False


def _validate_url(url: str) -> str:
    """Validate and normalize a URL, blocking SSRF vectors.

    Returns the validated URL or raises ``ValueError``.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}. Only http/https allowed.")
    if not parsed.hostname:
        raise ValueError("URL has no hostname.")
    if _is_private_ip(parsed.hostname):
        raise ValueError(f"Access to private/internal addresses is blocked: {parsed.hostname}")
    return url


class WebAgent(BaseAgent):
    name: ClassVar[str] = "Web Agent"
    slug: ClassVar[str] = "web"
    category: ClassVar[str] = "Productivity"
    description: ClassVar[str] = (
        "Browse URLs, take screenshots, extract content, and summarize web pages."
    )
    capabilities: ClassVar[list[str]] = [
        "web",
        "screenshot",
        "browse",
        "scrape",
        "summarize",
        "link",
        "preview",
        "monitor",
        "watch",
        "url",
        "page",
        "website",
    ]
    instructions: ClassVar[str] = (
        "You are a web browsing agent. You can take screenshots of web pages, "
        "extract readable content, summarize articles, and generate rich link previews.\n\n"
        "Available tools:\n"
        "- screenshot: Take a full-page screenshot of a URL. Returns the file path.\n"
        "- get_page_content: Extract the main readable text from a URL.\n"
        "- summarize_page: Get an LLM-powered summary of a web page.\n"
        "- get_link_preview: Get title, description, and image metadata for a URL.\n"
        "- watch_page: Register a page to watch for changes (returns confirmation).\n\n"
        "IMPORTANT:\n"
        "- All URLs must be http or https. Internal/private IPs are blocked for security.\n"
        "- If the user provides a URL, use the appropriate tool based on their intent.\n"
        "- For 'summarize' requests, prefer summarize_page over get_page_content.\n"
        "- For 'what does this page say' requests, use get_page_content.\n"
        "- When the screenshot tool returns a markdown image (![...](/api/v1/media/...)), "
        "you MUST include that EXACT markdown image in your response. "
        "Never replace the /api/v1/media/ URL with the original page URL.\n"
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[dict[str, Any], str] = Agent(
            deps_type=dict,
            system_prompt=self.get_system_prompt(),
        )
        settings = self.settings
        agent_ref = self

        @agent.tool
        async def screenshot(ctx: RunContext[dict[str, Any]], url: str) -> str:
            """Take a screenshot of a web page and return it as a markdown image."""
            url = _validate_url(url)
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                return "Error: playwright is not installed. Run: pip install playwright && playwright install chromium"

            screenshots_dir = Path(settings.web_screenshots_dir)
            screenshots_dir.mkdir(parents=True, exist_ok=True)

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.web_playwright_headless)
                context = await browser.new_context(
                    viewport={
                        "width": settings.web_max_screenshot_width,
                        "height": settings.web_max_screenshot_height,
                    },
                    user_agent=settings.web_user_agent,
                )
                page = await context.new_page()
                try:
                    await page.goto(url, timeout=settings.web_timeout_seconds * 1000)
                    await page.wait_for_load_state(
                        "networkidle", timeout=settings.web_timeout_seconds * 1000
                    )
                except Exception:
                    pass  # best-effort; take screenshot of whatever loaded

                fd, filepath = tempfile.mkstemp(suffix=".png", dir=str(screenshots_dir))
                os.close(fd)
                await page.screenshot(path=filepath, full_page=True)
                await browser.close()

            filename = Path(filepath).name
            image_url = f"/api/v1/media/{filename}"
            return f"Screenshot of {url}:\n\n![Screenshot of {url}]({image_url})"

        @agent.tool
        async def get_page_content(ctx: RunContext[dict[str, Any]], url: str) -> str:
            """Extract the main readable text content from a web page."""
            url = _validate_url(url)
            try:
                import trafilatura
            except ImportError:
                return "Error: trafilatura is not installed. Run: pip install trafilatura"

            async with httpx.AsyncClient(
                timeout=settings.web_timeout_seconds,
                headers={"User-Agent": settings.web_user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
            if not text:
                return f"Could not extract readable content from {url}"
            # Truncate very long content
            max_chars = 8000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Content truncated]"
            return text

        @agent.tool
        async def summarize_page(ctx: RunContext[dict[str, Any]], url: str) -> str:
            """Get an LLM-powered summary of a web page."""
            url = _validate_url(url)
            try:
                import trafilatura
            except ImportError:
                return "Error: trafilatura is not installed."

            async with httpx.AsyncClient(
                timeout=settings.web_timeout_seconds,
                headers={"User-Agent": settings.web_user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
            if not text:
                return f"Could not extract content from {url} to summarize."

            # Truncate for LLM context
            max_chars = 6000
            if len(text) > max_chars:
                text = text[:max_chars]

            summary = await agent_ref.ask_llm(
                f"Summarize the following web page content concisely:\n\n{text}",
            )
            return summary

        @agent.tool
        async def get_link_preview(ctx: RunContext[dict[str, Any]], url: str) -> dict[str, str]:
            """Get title, description, and image metadata for a URL (link preview)."""
            url = _validate_url(url)
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                return {"error": "beautifulsoup4 is not installed."}

            async with httpx.AsyncClient(
                timeout=settings.web_timeout_seconds,
                headers={"User-Agent": settings.web_user_agent},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            def _meta(property_name: str) -> str:
                tag = soup.find("meta", attrs={"property": property_name}) or soup.find(
                    "meta", attrs={"name": property_name}
                )
                return tag.get("content", "") if tag else ""

            title = _meta("og:title") or (soup.title.string if soup.title else "")
            description = _meta("og:description") or _meta("description")
            image = _meta("og:image")

            return {
                "url": url,
                "title": title or "",
                "description": description or "",
                "image": image or "",
            }

        @agent.tool
        async def watch_page(
            ctx: RunContext[dict[str, Any]],
            url: str,
            css_selector: str = "body",
            interval_minutes: int = 60,
        ) -> str:
            """Register a page to watch for changes at a given interval."""
            url = _validate_url(url)
            return (
                f"Watch registered for {url} (selector: {css_selector}, "
                f"interval: every {interval_minutes} minutes). "
                "Note: Scheduled monitoring requires cron integration and will be "
                "available in a future update."
            )

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("WebAgent executing")
        try:
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="browse the web")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps={})
            return {"summary": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("WebAgent error")
            return {"summary": f"Web agent error: {exc}", "error": str(exc)}
