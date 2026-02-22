"""Gmail email management agent."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


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
    instructions: ClassVar[str] = (
        "You manage a Gmail inbox via the Gmail API (OAuth2 authenticated).\n\n"
        "Available tools:\n"
        "- list_messages: Search messages using Gmail query syntax (e.g. 'is:unread', "
        "'from:alice@example.com', 'subject:invoice'). Returns up to 10 messages with "
        "sender, subject, and date.\n"
        "- send_message: Send an email. Requires to, subject, and body.\n"
        "- trash_message: Move a message to trash by its message ID.\n"
        "- mark_message_read: Mark a message as read by its message ID.\n\n"
        "When listing messages, default to 'is:unread' unless the user specifies otherwise. "
        "Requires Gmail OAuth credentials configured via 'angie config gmail'."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def list_messages(
            ctx: RunContext[object], query: str = "is:unread", max_results: int = 20
        ) -> dict:
            """List Gmail messages matching a search query."""
            svc = ctx.deps
            user = "me"
            results = (
                svc.users().messages().list(userId=user, q=query, maxResults=max_results).execute()
            )
            messages = results.get("messages", [])
            items = []
            for m in messages[:10]:
                msg = (
                    svc.users().messages().get(userId=user, id=m["id"], format="metadata").execute()
                )
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                items.append(
                    {
                        "id": m["id"],
                        "from": headers.get("From", ""),
                        "subject": headers.get("Subject", ""),
                        "date": headers.get("Date", ""),
                    }
                )
            return {"messages": items, "total": results.get("resultSizeEstimate", 0)}

        @agent.tool
        def send_message(ctx: RunContext[object], to: str, subject: str, body: str) -> dict:
            """Send an email via Gmail."""
            import base64
            from email.mime.text import MIMEText

            svc = ctx.deps
            msg = MIMEText(body)
            msg["To"] = to
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return {"sent": True, "message_id": result["id"]}

        @agent.tool
        def trash_message(ctx: RunContext[object], message_id: str) -> dict:
            """Move a Gmail message to trash."""
            svc = ctx.deps
            svc.users().messages().trash(userId="me", id=message_id).execute()
            return {"trashed": True, "message_id": message_id}

        @agent.tool
        def mark_message_read(ctx: RunContext[object], message_id: str) -> dict:
            """Mark a Gmail message as read."""
            svc = ctx.deps
            svc.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"marked_read": True, "message_id": message_id}

        return agent

    def _build_service(self, creds_data: dict[str, str] | None = None) -> Any:
        """Build a Gmail API service using stored OAuth credentials."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/gmail.modify"]

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
            creds_file = os.environ.get("GMAIL_CREDENTIALS_FILE", "gmail_credentials.json")  # noqa: F841
            token_file = os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json")
            from pathlib import Path

            if Path(token_file).exists():
                creds = Credentials.from_authorized_user_file(token_file, scopes)
            else:
                raise RuntimeError(
                    f"Gmail token not found at {token_file}. Run 'angie config gmail' to authenticate."
                )
        return build("gmail", "v1", credentials=creds)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        self.logger.info("GmailAgent executing")
        try:
            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "gmail")
            svc = await asyncio.get_event_loop().run_in_executor(None, self._build_service, creds)
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="list unread emails")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=svc)
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("GmailAgent error")
            return {"error": str(exc)}
