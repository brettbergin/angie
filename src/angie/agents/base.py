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
        self._copilot_session = None
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

    async def _get_copilot_session(self):
        """Lazily initialize a copilot-sdk session."""
        if self._copilot_session is None:
            try:
                from copilot import CopilotClient  # type: ignore[import]

                client = CopilotClient()
                await client.start()
                self._copilot_session = await client.create_session(
                    {
                        "model": self.settings.copilot_model,
                        "streaming": False,
                    }
                )
            except ImportError:
                self.logger.warning("copilot-sdk not available, falling back to pydantic-ai only")
        return self._copilot_session

    async def ask_llm(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt to the LLM and return the response string."""
        from pydantic_ai import Agent  # type: ignore[import]

        system_prompt = system or self.get_system_prompt()
        agent = Agent(
            model=f"openai:{self.settings.copilot_model}",
            system_prompt=system_prompt,
        )
        result = await agent.run(prompt)
        return str(result.data)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} slug={self.slug!r}>"
