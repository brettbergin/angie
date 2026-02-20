"""Email spam detection and deletion across providers agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent

SPAM_KEYWORDS = ["unsubscribe", "click here", "winner", "free money", "limited offer", "act now"]


class SpamAgent(BaseAgent):
    name: ClassVar[str] = "SpamAgent"
    slug: ClassVar[str] = "email-spam"
    description: ClassVar[str] = "Email spam detection and deletion across providers."
    capabilities: ClassVar[list[str]] = ["spam", "spam email", "delete spam", "clean inbox"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "scan")
        self.logger.info("SpamAgent action=%s", action)

        if action == "scan":
            return await self._scan(task.get("input_data", {}))
        if action == "delete_spam":
            return await self._delete_spam(task.get("input_data", {}))
        return {"error": f"Unknown action: {action}"}

    async def _scan(self, data: dict[str, Any]) -> dict[str, Any]:
        """Scan Gmail inbox for likely spam using keyword heuristics."""
        try:
            from angie.agents.email.gmail import GmailAgent

            gmail = GmailAgent()
            result = await gmail.execute({"input_data": {"action": "list", "query": "is:unread"}})
            messages = result.get("messages", [])
            spam = []
            for msg in messages:
                subject = msg.get("subject", "").lower()
                sender = msg.get("from", "").lower()
                if any(kw in subject for kw in SPAM_KEYWORDS):
                    spam.append({"id": msg["id"], "subject": msg.get("subject"), "from": msg.get("from")})
            return {"spam_found": len(spam), "items": spam}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    async def _delete_spam(self, data: dict[str, Any]) -> dict[str, Any]:
        """Trash messages by their IDs."""
        try:
            from angie.agents.email.gmail import GmailAgent

            gmail = GmailAgent()
            ids = data.get("message_ids", [])
            for mid in ids:
                await gmail.execute({"input_data": {"action": "trash", "message_id": mid}})
            return {"trashed": len(ids), "message_ids": ids}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

