"""Office 365 email management agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class OutlookAgent(BaseAgent):
    name: ClassVar[str] = "OutlookAgent"
    slug: ClassVar[str] = "outlook"
    description: ClassVar[str] = "Office 365 email management."
    capabilities: ClassVar[list[str]] = ["outlook", "office365", "email", "send email"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
