"""UniFi network management agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class UbiquitiAgent(BaseAgent):
    name: ClassVar[str] = "UbiquitiAgent"
    slug: ClassVar[str] = "ubiquiti"
    description: ClassVar[str] = "UniFi network management."
    capabilities: ClassVar[list[str]] = ["network", "wifi", "unifi", "ubiquiti", "clients", "bandwidth"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
