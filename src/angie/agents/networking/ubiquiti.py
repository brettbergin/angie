"""UniFi network management agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class UbiquitiAgent(BaseAgent):
    name: ClassVar[str] = "UbiquitiAgent"
    slug: ClassVar[str] = "ubiquiti"
    category: ClassVar[str] = "Smart Home Agents"
    description: ClassVar[str] = "UniFi network management."
    capabilities: ClassVar[list[str]] = [
        "network",
        "wifi",
        "unifi",
        "ubiquiti",
        "clients",
        "bandwidth",
    ]
    instructions: ClassVar[str] = (
        "You manage a UniFi network via the UniFi Controller API.\n\n"
        "Available tools:\n"
        "- list_clients: List all connected network clients.\n"
        "- get_network_stats: Get current network throughput and statistics.\n\n"
        "Note: This agent is not yet fully implemented. Operations will return a "
        "'not_implemented' status until the pyunifi/aiounifi SDK integration is complete."
    )

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
