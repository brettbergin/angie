"""Gmail email management agent."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class GmailAgent(BaseAgent):
    name: ClassVar[str] = "GmailAgent"
    slug: ClassVar[str] = "gmail"
    description: ClassVar[str] = "Gmail email management."
    capabilities: ClassVar[list[str]] = [
        "gmail",
        "email",
        "send email",
        "read email",
        "search email",
        "inbox",
    ]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")
        self.logger.info("GmailAgent action=%s", action)
        try:
            return await self._dispatch(action, task.get("input_data", {}))
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GmailAgent error")
            return {"error": str(exc)}

    def _build_service(self) -> Any:
        """Build a Gmail API service using a service account or OAuth credentials."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds_file = os.environ.get("GMAIL_CREDENTIALS_FILE", "gmail_credentials.json")
        token_file = os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json")
        scopes = ["https://www.googleapis.com/auth/gmail.modify"]

        import json
        from pathlib import Path

        if Path(token_file).exists():
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        else:
            raise RuntimeError(
                f"Gmail token not found at {token_file}. "
                "Run 'angie config gmail' to authenticate."
            )
        return build("gmail", "v1", credentials=creds)

    async def _dispatch(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self._dispatch_sync, action, data
        )

    def _dispatch_sync(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        import base64
        from email.mime.text import MIMEText

        svc = self._build_service()
        user = "me"

        if action == "list":
            q = data.get("query", "is:unread")
            results = svc.users().messages().list(userId=user, q=q, maxResults=20).execute()
            messages = results.get("messages", [])
            items = []
            for m in messages[:10]:
                msg = svc.users().messages().get(userId=user, id=m["id"], format="metadata").execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                items.append({
                    "id": m["id"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                })
            return {"messages": items, "total": results.get("resultSizeEstimate", 0)}

        if action == "send":
            to = data.get("to", "")
            subject = data.get("subject", "")
            body = data.get("body", "")
            msg = MIMEText(body)
            msg["To"] = to
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = svc.users().messages().send(userId=user, body={"raw": raw}).execute()
            return {"sent": True, "message_id": result["id"]}

        if action == "trash":
            mid = data.get("message_id", "")
            svc.users().messages().trash(userId=user, id=mid).execute()
            return {"trashed": True, "message_id": mid}

        if action == "mark_read":
            mid = data.get("message_id", "")
            svc.users().messages().modify(userId=user, id=mid, body={"removeLabelIds": ["UNREAD"]}).execute()
            return {"marked_read": True, "message_id": mid}

        return {"error": f"Unknown action: {action}"}

