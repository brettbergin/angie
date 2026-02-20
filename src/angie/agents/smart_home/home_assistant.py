"""Home Assistant smart home control agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class HomeAssistantAgent(BaseAgent):
    name: ClassVar[str] = "HomeAssistantAgent"
    slug: ClassVar[str] = "home-assistant"
    description: ClassVar[str] = "Home Assistant smart home control."
    capabilities: ClassVar[list[str]] = ["home assistant", "smart home", "automation", "thermostat"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
