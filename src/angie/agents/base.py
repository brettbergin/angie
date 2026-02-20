"""BaseAgent — pydantic-ai agent wrapper with copilot-sdk LLM backend."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from angie.config import get_settings
from angie.core.prompts import get_prompt_manager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all Angie agents.

    Each agent wraps:
    - An external service SDK (Gmail, Slack, phue, etc.)
    - A pydantic-ai Agent for structured LLM interactions
    - A copilot-sdk session for the underlying LLM engine
    """

    # Subclasses must declare these
    name: ClassVar[str]
    slug: ClassVar[str]
    description: ClassVar[str]
    capabilities: ClassVar[list[str]] = []

    def __init__(self) -> None:
        self.settings = get_settings()
        self.prompt_manager = get_prompt_manager()
        self._pydantic_agent = None
        self.logger = logging.getLogger(f"angie.agents.{self.slug}")

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute the task and return a result dict."""
        ...

    def can_handle(self, task: dict[str, Any]) -> bool:
        """Return True if this agent can handle the given task."""
        task_slug = task.get("agent_slug")
        if task_slug:
            return task_slug == self.slug
        # Fallback: check if any capability keyword is in task title
        title = task.get("title", "").lower()
        return any(cap.lower() in title for cap in self.capabilities)

    def get_system_prompt(self) -> str:
        return self.prompt_manager.compose_for_agent(self.slug)


    async def ask_llm(
        self,
        prompt: str,
        system: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Send a prompt through the full prompt hierarchy to the LLM."""
        from pydantic_ai import Agent

        from angie.llm import get_llm_model

        if system is None:
            system = self.get_system_prompt()

        try:
            model = get_llm_model()
            agent = Agent(model=model, system_prompt=system)
            result = await agent.run(prompt)
            return str(result.output)
        except Exception as exc:
            self.logger.error("LLM call failed: %s", exc)
            raise

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} slug={self.slug!r}>"
