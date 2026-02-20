"""Spotify music control agent."""

from __future__ import annotations

from typing import Any, ClassVar

from angie.agents.base import BaseAgent


class SpotifyAgent(BaseAgent):
    name: ClassVar[str] = "SpotifyAgent"
    slug: ClassVar[str] = "spotify"
    description: ClassVar[str] = "Spotify music control."
    capabilities: ClassVar[list[str]] = ["spotify", "music", "play", "pause", "playlist", "song"]

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        # TODO: implement using SDK
        self.logger.info("%s executing task: %s", self.name, task.get("title"))
        return {"status": "not_implemented", "agent": self.slug}
