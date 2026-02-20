"""UniFi network management agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class UbiquitiAgent(BaseAgent):
    name: ClassVar[str] = "UbiquitiAgent"
    slug: ClassVar[str] = "ubiquiti"
    description: ClassVar[str] = "UniFi network management."
    capabilities: ClassVar[list[str]] = [
        "network",
        "wifi",
        "unifi",
        "ubiquiti",
        "clients",
        "bandwidth",
    ]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        def list_clients() -> dict:
            """List all connected UniFi network clients."""
            # TODO: implement using pyunifi / aiounifi SDK
            return {"status": "not_implemented", "agent": "ubiquiti"}

        @agent.tool_plain
        def get_network_stats() -> dict:
            """Get current UniFi network throughput and statistics."""
            # TODO: implement using pyunifi / aiounifi SDK
            return {"status": "not_implemented", "agent": "ubiquiti"}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
