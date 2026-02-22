"""Google Calendar management agent."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class GoogleCalendarAgent(BaseAgent):
    name: ClassVar[str] = "GoogleCalendarAgent"
    slug: ClassVar[str] = "google-calendar"
    category: ClassVar[str] = "Planning Agents"
    description: ClassVar[str] = "Google Calendar management."
    capabilities: ClassVar[list[str]] = [
        "calendar",
        "event",
        "schedule",
        "meeting",
        "appointment",
        "reminder",
        "upcoming events",
    ]
    instructions: ClassVar[str] = (
        "You manage Google Calendar events via the Calendar API (OAuth2 authenticated).\n\n"
        "Available tools:\n"
        "- list_upcoming_events: List events within the next N days (default: 7). "
        "Supports specifying a calendar_id (default: primary).\n"
        "- create_event: Create an event with summary, start/end times (ISO 8601), "
        "optional description, timezone, and calendar_id.\n"
        "- delete_event: Delete an event by its ID.\n\n"
        "When creating events, ensure start and end times are in ISO 8601 format. "
        "Requires Google Calendar OAuth credentials configured via 'angie config gmail'."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def list_upcoming_events(
            ctx: RunContext[object], calendar_id: str = "primary", days_ahead: int = 7
        ) -> dict:
            """List upcoming Google Calendar events within the next N days."""
            svc = ctx.deps
            now = datetime.now(UTC).isoformat()
            end = (datetime.now(UTC) + timedelta(days=days_ahead)).isoformat()
            result = (
                svc.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    timeMax=end,
                    maxResults=20,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = [
                {
                    "id": e["id"],
                    "summary": e.get("summary", "(no title)"),
                    "start": e["start"].get("dateTime", e["start"].get("date")),
                    "end": e["end"].get("dateTime", e["end"].get("date")),
                }
                for e in result.get("items", [])
            ]
            return {"events": events}

        @agent.tool
        def create_event(
            ctx: RunContext[object],
            summary: str,
            start: str,
            end: str,
            description: str = "",
            timezone: str = "UTC",
            calendar_id: str = "primary",
        ) -> dict:
            """Create a new Google Calendar event."""
            svc = ctx.deps
            event_body = {
                "summary": summary,
                "start": {"dateTime": start, "timeZone": timezone},
                "end": {"dateTime": end, "timeZone": timezone},
                "description": description,
            }
            result = svc.events().insert(calendarId=calendar_id, body=event_body).execute()
            return {"created": True, "event_id": result["id"], "link": result.get("htmlLink", "")}

        @agent.tool
        def delete_event(
            ctx: RunContext[object], event_id: str, calendar_id: str = "primary"
        ) -> dict:
            """Delete a Google Calendar event by its ID."""
            svc = ctx.deps
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"deleted": True, "event_id": event_id}

        return agent

    def _build_service(self, creds_data: dict[str, str] | None = None) -> Any:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/calendar"]

        if creds_data:
            token = creds_data.get("access_token") or creds_data.get("token")
        else:
            token = None

        if token:
            creds = Credentials(
                token=token,
                refresh_token=creds_data.get("refresh_token") if creds_data else None,
                token_uri=(
                    creds_data.get("token_uri", "https://oauth2.googleapis.com/token")
                    if creds_data
                    else "https://oauth2.googleapis.com/token"
                ),
                client_id=creds_data.get("client_id") if creds_data else None,
                client_secret=creds_data.get("client_secret") if creds_data else None,
                scopes=scopes,
            )
        else:
            token_file = os.environ.get("GCAL_TOKEN_FILE", "gcal_token.json")
            from pathlib import Path

            if not Path(token_file).exists():
                raise RuntimeError(f"Google Calendar token not found at {token_file}.")
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        return build("calendar", "v3", credentials=creds)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        self.logger.info("GoogleCalendarAgent executing")
        try:
            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "gcal")
            svc = await asyncio.get_event_loop().run_in_executor(None, self._build_service, creds)
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="list upcoming events")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=svc)
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GoogleCalendarAgent error")
            return {"error": str(exc)}
