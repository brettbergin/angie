"""Service registry and connection helpers for credential management."""

from __future__ import annotations

import logging
from typing import Any

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
    "spotify": {
        "name": "Spotify",
        "description": "Music playback — play, pause, skip, search, queue",
        "auth_type": "oauth2",
        "color": "#1DB954",
        "fields": [
            {"key": "client_id", "label": "Client ID", "type": "text"},
            {"key": "client_secret", "label": "Client Secret", "type": "password"},
            {"key": "access_token", "label": "Access Token", "type": "password"},
            {"key": "refresh_token", "label": "Refresh Token", "type": "password"},
        ],
        "test_endpoint": "https://api.spotify.com/v1/me",
        "agent_slug": "spotify",
    },
    "gmail": {
        "name": "Gmail",
        "description": "Email management — read, send, organize, spam detection",
        "auth_type": "oauth2",
        "color": "#EA4335",
        "fields": [
            {"key": "client_id", "label": "Client ID", "type": "text"},
            {"key": "client_secret", "label": "Client Secret", "type": "password"},
            {"key": "access_token", "label": "Access Token", "type": "password"},
            {"key": "refresh_token", "label": "Refresh Token", "type": "password"},
        ],
        "test_endpoint": "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        "agent_slug": "gmail",
    },
    "gcal": {
        "name": "Google Calendar",
        "description": "Calendar management — events, scheduling, availability",
        "auth_type": "oauth2",
        "color": "#4285F4",
        "fields": [
            {"key": "client_id", "label": "Client ID", "type": "text"},
            {"key": "client_secret", "label": "Client Secret", "type": "password"},
            {"key": "access_token", "label": "Access Token", "type": "password"},
            {"key": "refresh_token", "label": "Refresh Token", "type": "password"},
        ],
        "test_endpoint": "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        "agent_slug": "gcal",
    },
    "hue": {
        "name": "Philips Hue",
        "description": "Smart lighting — control lights, scenes, and brightness",
        "auth_type": "credentials",
        "color": "#0065D3",
        "fields": [
            {"key": "bridge_ip", "label": "Bridge IP Address", "type": "text"},
            {"key": "username", "label": "API Username / Key", "type": "password"},
        ],
        "test_endpoint": None,
        "agent_slug": "hue",
    },
    "home_assistant": {
        "name": "Home Assistant",
        "description": "Home automation — devices, scenes, automations",
        "auth_type": "token",
        "color": "#41BDF5",
        "fields": [
            {"key": "url", "label": "Home Assistant URL", "type": "text"},
            {"key": "token", "label": "Long-Lived Access Token", "type": "password"},
        ],
        "test_endpoint": "/api/",
        "agent_slug": "home-assistant",
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
    "unifi": {
        "name": "UniFi Network",
        "description": "Network management — devices, clients, bandwidth stats",
        "auth_type": "credentials",
        "color": "#006FFF",
        "fields": [
            {"key": "host", "label": "Controller URL", "type": "text"},
            {"key": "username", "label": "Username", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
        "test_endpoint": None,
        "agent_slug": "ubiquiti",
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
        from angie.models.connection import Connection

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.user_id == user_id,
                    Connection.service_type == service_type,
                    Connection.status == "connected",
                )
            )
            return result.scalars().first()
    except Exception as exc:
        logger.warning("Could not load connection for %s/%s: %s", user_id, service_type, exc)
        return None


async def test_connection_validity(credentials: dict, service_type: str) -> tuple[bool, str]:
    """Test connection by calling the service's test endpoint."""
    import httpx

    service = SERVICE_REGISTRY.get(service_type)
    if not service or not service.get("test_endpoint"):
        return True, "No test endpoint available — credentials saved"

    test_url = service["test_endpoint"]
    auth_type = service["auth_type"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers: dict[str, str] = {}

            if service_type == "github":
                token = credentials.get("personal_access_token", "")
                headers["Authorization"] = f"Bearer {token}"
                headers["Accept"] = "application/vnd.github+json"
            elif service_type in ("spotify", "gmail", "gcal"):
                token = credentials.get("access_token", "")
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "token" and service_type == "home_assistant":
                base_url = credentials.get("url", "").rstrip("/")
                test_url = f"{base_url}{test_url}"
                headers["Authorization"] = f"Bearer {credentials.get('token', '')}"
            elif service_type == "slack":
                headers["Authorization"] = f"Bearer {credentials.get('bot_token', '')}"
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
    except Exception as exc:
        return False, f"Connection failed: {exc}"
