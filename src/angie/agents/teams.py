"""Runtime team resolver — selects agents based on team membership."""

from __future__ import annotations

from typing import TYPE_CHECKING

from angie.agents.registry import get_registry
from angie.core.tasks import AngieTask

if TYPE_CHECKING:
    from angie.agents.base import BaseAgent


class TeamResolver:
    """Resolve which agents should handle a task for a given team."""

    def __init__(self, team_slug: str, agent_slugs: list[str]) -> None:
        self.team_slug = team_slug
        self.agent_slugs = agent_slugs

    def agents(self) -> list[BaseAgent]:
        registry = get_registry()
        return [a for a in registry.all() if a.slug in self.agent_slugs]

    def resolve(self, task: AngieTask) -> BaseAgent | None:
        """Return the first agent in this team that can handle the task."""
        for agent in self.agents():
            if agent.can_handle(task):
                return agent
        return None

    async def execute(self, task: AngieTask) -> dict:
        """Execute a task against this team, trying agents in priority order."""
        results: list[dict] = []
        for agent in self.agents():
            if agent.can_handle(task):
                result = await agent.execute(task)
                results.append({"agent": agent.slug, "result": result})
                # Stop after first successful execution unless task requires fan-out
                if result.get("status") != "failure":
                    break
        return {"team": self.team_slug, "results": results}


_teams: dict[str, TeamResolver] = {}


def register_team(slug: str, agent_slugs: list[str]) -> TeamResolver:
    """Register a team with the given agent slugs."""
    team = TeamResolver(slug, agent_slugs)
    _teams[slug] = team
    return team


def get_team(slug: str) -> TeamResolver | None:
    return _teams.get(slug)


def all_teams() -> dict[str, TeamResolver]:
    return dict(_teams)
