"""Agent registry — auto-discovery and lookup."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from angie.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# All agent module paths — add new agents here
AGENT_MODULES = [
    "angie.agents.system.cron",
    "angie.agents.system.task_manager",
    "angie.agents.system.workflow_manager",
    "angie.agents.system.event_manager",
    "angie.agents.email.gmail",
    "angie.agents.email.outlook",
    "angie.agents.email.yahoo",
    "angie.agents.email.spam",
    "angie.agents.email.correspondence",
    "angie.agents.calendar.gcal",
    "angie.agents.smart_home.hue",
    "angie.agents.smart_home.home_assistant",
    "angie.agents.networking.ubiquiti",
    "angie.agents.media.spotify",
    "angie.agents.dev.github",
    "angie.agents.dev.software_dev",
    "angie.agents.productivity.web",
    "angie.agents.productivity.reminders",
]


class AgentRegistry:
    """Registry for discovering and retrieving agents by slug or capability."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._loaded = False

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.slug] = agent
        logger.debug("Registered agent: %s", agent.slug)

    def load_all(self) -> None:
        """Import all known agent modules and register any BaseAgent subclasses found."""
        if self._loaded:
            return
        for module_path in AGENT_MODULES:
            try:
                module = importlib.import_module(module_path)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseAgent)
                        and attr is not BaseAgent
                        and hasattr(attr, "slug")
                    ):
                        self.register(attr())
            except ImportError as e:
                logger.warning("Could not load agent module %s: %s", module_path, e)
            except Exception as e:
                logger.exception("Error loading agent module %s: %s", module_path, e)
        self._loaded = True

    def get(self, slug: str) -> BaseAgent | None:
        self.load_all()
        return self._agents.get(slug)

    def resolve(self, task: dict[str, Any]) -> BaseAgent | None:
        """Find the first agent that can handle this task."""
        self.load_all()
        for agent in self._agents.values():
            if agent.can_handle(task):
                return agent
        return None

    def list_all(self) -> list[BaseAgent]:
        self.load_all()
        return list(self._agents.values())

    def list_enabled(self) -> list[BaseAgent]:
        return self.list_all()  # All loaded agents are enabled by default


_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def agent(cls: type[BaseAgent]) -> type[BaseAgent]:
    """Class decorator to auto-register an agent on import."""
    get_registry().register(cls())
    return cls
