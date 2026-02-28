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
    "angie.agents.dev.github",
    "angie.agents.dev.software_dev",
    "angie.agents.productivity.web",
    "angie.agents.lifestyle.weather",
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
        """Find the best agent by confidence score. Falls back to LLM routing."""
        self.load_all()

        # Confidence scoring
        scored = [(agent, agent.confidence(task)) for agent in self._agents.values()]
        scored.sort(key=lambda x: x[1], reverse=True)

        if scored and scored[0][1] >= 0.5:
            return scored[0][0]

        # LLM-based routing (fallback for ambiguous tasks)
        return self._llm_route_sync(task)

    def _llm_route_sync(self, task: dict[str, Any]) -> BaseAgent | None:
        """Synchronously try LLM routing."""
        import asyncio
        import concurrent.futures

        try:
            return asyncio.run(self._llm_route(task))
        except RuntimeError:
            # Already inside a running event loop — run in a separate thread
            # where asyncio.run() is safe to call.
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._llm_route(task))
                    return future.result(timeout=30)
            except Exception:
                logger.debug("LLM routing failed", exc_info=True)
                return None

    async def _llm_route(self, task: dict[str, Any]) -> BaseAgent | None:
        """Ask the LLM which agent should handle this task."""
        from angie.llm import get_llm_model, is_llm_configured

        if not is_llm_configured():
            return None

        agent_descriptions = "\n".join(
            f"- {a.slug}: {a.description} (capabilities: {', '.join(a.capabilities)})"
            for a in self._agents.values()
        )
        prompt = (
            f"Given this task: {task.get('title', '')}\n"
            f"User text: {task.get('input_data', {}).get('text', '')}\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            f"Which agent slug should handle this? Reply with just the slug, "
            f"or 'none' if no agent fits."
        )
        try:
            from pydantic_ai import Agent

            agent = Agent(
                system_prompt="You are a task router. Reply with only an agent slug or 'none'."
            )
            result = await agent.run(prompt, model=get_llm_model())
            slug = str(result.output).strip().lower()
            return self._agents.get(slug)
        except Exception:
            logger.debug("LLM route failed", exc_info=True)
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
