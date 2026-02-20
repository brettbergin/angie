"""Office 365 email management agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class OutlookAgent(BaseAgent):
    name: ClassVar[str] = "OutlookAgent"
    slug: ClassVar[str] = "outlook"
    description: ClassVar[str] = "Office 365 email management."
    capabilities: ClassVar[list[str]] = ["outlook", "office365", "email", "send email"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def list_messages(folder: str = "inbox", max_results: int = 20) -> dict:
            """List Office 365 email messages from a folder."""
            # TODO: implement using O365 SDK
            return {"status": "not_implemented", "agent": "outlook"}

        @agent.tool_plain
        def send_message(to: str, subject: str, body: str) -> dict:
            """Send an email via Office 365."""
            # TODO: implement using O365 SDK
            return {"status": "not_implemented", "agent": "outlook"}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
