"""Yahoo Mail management agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class YahooMailAgent(BaseAgent):
    name: ClassVar[str] = "YahooMailAgent"
    slug: ClassVar[str] = "yahoo-mail"
    category: ClassVar[str] = "Communication Agents"
    description: ClassVar[str] = "Yahoo Mail management."
    capabilities: ClassVar[list[str]] = ["yahoo", "yahoo mail", "email"]
    instructions: ClassVar[str] = (
        "You manage a Yahoo Mail inbox.\n\n"
        "Available tools:\n"
        "- list_messages: List emails from a folder (default: inbox).\n"
        "- send_message: Send an email. Requires to, subject, and body.\n\n"
        "Note: This agent is not yet fully implemented. Operations will return a "
        "'not_implemented' status until the IMAP/SMTP integration is complete."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def list_messages(folder: str = "inbox", max_results: int = 20) -> dict:
            """List Yahoo Mail messages from a folder."""
            # TODO: implement using IMAP
            return {"status": "not_implemented", "agent": "yahoo-mail"}

        @agent.tool_plain
        def send_message(to: str, subject: str, body: str) -> dict:
            """Send an email via Yahoo Mail."""
            # TODO: implement using SMTP
            return {"status": "not_implemented", "agent": "yahoo-mail"}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
