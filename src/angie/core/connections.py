"""Service registry and connection helpers for credential management."""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SERVICE_REGISTRY: dict[str, dict[str, Any]] = {
    "github": {
        "name": "GitHub",
        "description": "Repository management — PRs, issues, code review",
        "auth_type": "api_key",
        "color": "#333333",
        "fields": [
            {"key": "personal_access_token", "label": "Personal Access Token", "type": "password"},
        ],
        "test_endpoint": "https://api.github.com/user",
        "agent_slug": "github",
    },
    "slack": {
        "name": "Slack",
        "description": "Team messaging — send and receive messages via Slack",
        "auth_type": "token",
        "color": "#4A154B",
        "fields": [
            {"key": "bot_token", "label": "Bot Token (xoxb-…)", "type": "password"},
            {"key": "app_token", "label": "App Token (xapp-…)", "type": "password"},
        ],
        "test_endpoint": "https://slack.com/api/auth.test",
        "agent_slug": None,
    },
    "discord": {
        "name": "Discord",
        "description": "Community messaging — Discord bot integration",
        "auth_type": "token",
        "color": "#5865F2",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "password"},
        ],
        "test_endpoint": "https://discord.com/api/v10/users/@me",
        "agent_slug": None,
    },
    "bluebubbles": {
        "name": "iMessage (BlueBubbles)",
        "description": "iMessage integration via BlueBubbles server",
        "auth_type": "credentials",
        "color": "#34C759",
        "fields": [
            {"key": "url", "label": "BlueBubbles Server URL", "type": "text"},
            {"key": "password", "label": "Server Password", "type": "password"},
        ],
        "test_endpoint": None,
        "agent_slug": None,
    },
    "email_smtp": {
        "name": "Email (SMTP/IMAP)",
        "description": "Generic email — send and receive via SMTP/IMAP",
        "auth_type": "credentials",
        "color": "#FF6600",
        "fields": [
            {"key": "smtp_host", "label": "SMTP Host", "type": "text"},
            {"key": "imap_host", "label": "IMAP Host", "type": "text"},
            {"key": "username", "label": "Username", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
        "test_endpoint": None,
        "agent_slug": None,
    },
    "openweathermap": {
        "name": "OpenWeatherMap",
        "description": "Weather data — current conditions, forecasts, and severe weather alerts",
        "auth_type": "api_key",
        "color": "#EB6E4B",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password"},
        ],
        "test_endpoint": "https://api.openweathermap.org/data/2.5/weather?q=London&appid={api_key}",
        "agent_slug": "weather",
    },
}


def get_service_registry() -> dict[str, dict[str, Any]]:
    """Return the full service registry."""
    return SERVICE_REGISTRY


async def get_connection(user_id: str, service_type: str):
    """Load a user's connection for a given service from the database."""
    try:
        from sqlalchemy import select

        from angie.db.session import get_session_factory
        from angie.models.connection import Connection, ConnectionStatus

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.user_id == user_id,
                    Connection.service_type == service_type,
                    Connection.status == ConnectionStatus.CONNECTED,
                )
            )
            return result.scalars().first()
    except Exception as exc:
        logger.warning("Could not load connection for %s/%s: %s", user_id, service_type, exc)
        return None


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate a user-supplied URL to mitigate SSRF risks.

    Only http/https schemes are allowed. The URL must be parseable.
    Returns (is_valid, error_message).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    if parsed.scheme not in ("http", "https"):
        return False, "URL must use http or https scheme"

    hostname = parsed.hostname or ""
    if not hostname:
        return False, "URL must include a hostname"

    # Resolve hostname to check for private/loopback addresses
    try:
        resolved_ip = socket.getaddrinfo(hostname, None)[0][4][0]
        addr = ipaddress.ip_address(resolved_ip)
        if addr.is_loopback or addr.is_link_local or addr.is_multicast:
            return False, "URL resolves to a reserved address"
    except (socket.gaierror, ValueError):
        # If we can't resolve (e.g. DNS failure), allow it — the HTTP call will fail anyway
        pass

    return True, ""


async def test_connection_validity(credentials: dict, service_type: str) -> tuple[bool, str]:
    """Test connection by calling the service's test endpoint."""
    import httpx

    service = SERVICE_REGISTRY.get(service_type)
    if not service or not service.get("test_endpoint"):
        return True, "No test endpoint available — credentials saved"

    test_url = service["test_endpoint"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers: dict[str, str] = {}

            if service_type == "github":
                token = credentials.get("personal_access_token", "")
                headers["Authorization"] = f"Bearer {token}"
                headers["Accept"] = "application/vnd.github+json"
            elif service_type == "slack":
                headers["Authorization"] = f"Bearer {credentials.get('bot_token', '')}"
            elif service_type == "openweathermap":
                api_key = credentials.get("api_key", "")
                test_url = test_url.replace("{api_key}", api_key)
            elif service_type == "discord":
                headers["Authorization"] = f"Bot {credentials.get('bot_token', '')}"
            else:
                return True, "No automated test available — credentials saved"

            resp = await client.get(test_url, headers=headers)
            if resp.status_code < 300:
                return True, "Connection successful"
            return False, f"Service returned HTTP {resp.status_code}"
    except httpx.TimeoutException:
        return False, "Connection timed out"
    except Exception:
        logger.exception(
            "Unexpected error while testing connection for service_type=%s", service_type
        )
        return False, "Connection failed due to an unexpected error"
