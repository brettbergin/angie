"""Context-aware email reply drafting agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class EmailCorrespondenceAgent(BaseAgent):
    name: ClassVar[str] = "EmailCorrespondenceAgent"
    slug: ClassVar[str] = "email-correspondence"
    description: ClassVar[str] = "Context-aware email reply drafting."
    capabilities: ClassVar[list[str]] = [
        "reply email",
        "draft email",
        "respond to email",
        "email reply",
        "compose email",
    ]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "draft_reply")
        self.logger.info("EmailCorrespondenceAgent action=%s", action)

        if action == "draft_reply":
            return await self._draft_reply(task.get("input_data", {}))
        if action == "send_reply":
            return await self._send_reply(task.get("input_data", {}))
        return {"error": f"Unknown action: {action}"}

    async def _draft_reply(self, data: dict[str, Any]) -> dict[str, Any]:
        """Use LLM to draft a reply to the given email content."""
        original_text = data.get("email_body", "")
        context = data.get("context", "")
        tone = data.get("tone", "professional")

        if not original_text:
            return {"error": "email_body is required"}

        from angie.llm import is_llm_configured

        if not is_llm_configured():
            return {"error": "LLM not configured — set GITHUB_TOKEN or OPENAI_API_KEY"}

        reply = await self.ask_llm(
            f"Draft a {tone} email reply to the following:\n\n{original_text}\n\nContext: {context}"
        )
        return {"draft": reply, "tone": tone}

    async def _send_reply(self, data: dict[str, Any]) -> dict[str, Any]:
        """Draft and immediately send via GmailAgent."""
        draft_result = await self._draft_reply(data)
        if "error" in draft_result:
            return draft_result

        from angie.agents.email.gmail import GmailAgent

        gmail = GmailAgent()
        return await gmail.execute({
            "input_data": {
                "action": "send",
                "to": data.get("reply_to", ""),
                "subject": f"Re: {data.get('subject', '')}",
                "body": draft_result["draft"],
            }
        })

