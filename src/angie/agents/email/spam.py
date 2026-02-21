"""Email spam detection and deletion across providers agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent

SPAM_KEYWORDS = ["unsubscribe", "click here", "winner", "free money", "limited offer", "act now"]


class SpamAgent(BaseAgent):
    name: ClassVar[str] = "SpamAgent"
    slug: ClassVar[str] = "email-spam"
    description: ClassVar[str] = "Email spam detection and deletion across providers."
    capabilities: ClassVar[list[str]] = ["spam", "spam email", "delete spam", "clean inbox"]
    instructions: ClassVar[str] = (
        "You detect and clean up spam emails across providers.\n\n"
        "Available tools:\n"
        "- scan_for_spam: Scan the Gmail inbox for likely spam using keyword heuristics "
        "(unsubscribe, click here, winner, free money, limited offer, act now). Returns "
        "a list of suspected spam messages with IDs and subjects.\n"
        "- delete_spam_messages: Trash a list of spam messages by their IDs.\n\n"
        "Always scan first to identify spam, present findings to the user, then delete "
        "only after confirmation."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        async def scan_for_spam() -> dict:
            """Scan the Gmail inbox for likely spam using keyword heuristics."""
            try:
                from angie.agents.email.gmail import GmailAgent

                gmail = GmailAgent()
                result = await gmail.execute({"input_data": {"intent": "list unread emails"}})
                messages = result.get("messages", [])
                spam = [
                    {"id": m["id"], "subject": m.get("subject"), "from": m.get("from")}
                    for m in messages
                    if any(kw in m.get("subject", "").lower() for kw in SPAM_KEYWORDS)
                ]
                return {"spam_found": len(spam), "items": spam}
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        @agent.tool_plain
        async def delete_spam_messages(message_ids: list) -> dict:
            """Trash a list of Gmail messages identified as spam."""
            try:
                from angie.agents.email.gmail import GmailAgent

                gmail = GmailAgent()
                for mid in message_ids:
                    await gmail.execute({"input_data": {"intent": f"trash message {mid}"}})
                return {"trashed": len(message_ids), "message_ids": message_ids}
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="scan inbox for spam")
        self.logger.info("SpamAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("SpamAgent error")
            return {"error": str(exc)}
