"""Google Calendar management agent."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class GoogleCalendarAgent(BaseAgent):
    name: ClassVar[str] = "GoogleCalendarAgent"
    slug: ClassVar[str] = "google-calendar"
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

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")
        self.logger.info("GoogleCalendarAgent action=%s", action)
        try:
            import asyncio

            return await asyncio.get_event_loop().run_in_executor(
                None, self._dispatch_sync, action, task.get("input_data", {})
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GoogleCalendarAgent error")
            return {"error": str(exc)}

    def _build_service(self) -> Any:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_file = os.environ.get("GCAL_TOKEN_FILE", "gcal_token.json")
        scopes = ["https://www.googleapis.com/auth/calendar"]
        from pathlib import Path

        if not Path(token_file).exists():
            raise RuntimeError(f"Google Calendar token not found at {token_file}.")
        creds = Credentials.from_authorized_user_file(token_file, scopes)
        return build("calendar", "v3", credentials=creds)

    def _dispatch_sync(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        svc = self._build_service()
        cal_id = data.get("calendar_id", "primary")

        if action == "list":
            now = datetime.now(timezone.utc).isoformat()
            end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            result = (
                svc.events()
                .list(
                    calendarId=cal_id,
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

        if action == "create":
            event_body = {
                "summary": data.get("summary", "New Event"),
                "start": {"dateTime": data.get("start"), "timeZone": data.get("timezone", "UTC")},
                "end": {"dateTime": data.get("end"), "timeZone": data.get("timezone", "UTC")},
                "description": data.get("description", ""),
            }
            result = svc.events().insert(calendarId=cal_id, body=event_body).execute()
            return {"created": True, "event_id": result["id"], "link": result.get("htmlLink", "")}

        if action == "delete":
            event_id = data.get("event_id", "")
            svc.events().delete(calendarId=cal_id, eventId=event_id).execute()
            return {"deleted": True, "event_id": event_id}

        return {"error": f"Unknown action: {action}"}

