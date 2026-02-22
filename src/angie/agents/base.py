"""BaseAgent — pydantic-ai agent wrapper with copilot-sdk LLM backend."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from angie.config import get_settings
from angie.core.prompts import get_prompt_manager

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all Angie agents.

    Each agent wraps:
    - An external service SDK (Gmail, Slack, phue, etc.)
    - A pydantic-ai Agent whose @tool functions call the SDK
    - A copilot-sdk session for the underlying LLM engine

    The LLM decides which tool(s) to invoke based on a natural-language
    *intent* extracted from the incoming task.  The pydantic-ai model is
    injected at `agent.run()` time (never stored on the Agent instance)
    so that Copilot token refreshes are always picked up automatically.
    """

    # Subclasses must declare these
    name: ClassVar[str]
    slug: ClassVar[str]
    description: ClassVar[str]
    capabilities: ClassVar[list[str]] = []
    instructions: ClassVar[str] = ""
    category: ClassVar[str] = "General"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.prompt_manager = get_prompt_manager()
        self._pydantic_agent: Agent | None = None
        self.logger = logging.getLogger(f"angie.agents.{self.slug}")

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute the task and return a result dict."""
        ...

    # ------------------------------------------------------------------
    # pydantic-ai agent wiring
    # ------------------------------------------------------------------

    def build_pydantic_agent(self) -> Agent:
        """Build a pydantic-ai Agent with @tool functions for this agent.

        Subclasses override this to register their SDK capabilities as
        ``@agent.tool`` (with ``RunContext[DepsT]``) or
        ``@agent.tool_plain`` (no deps) decorated functions.

        The Agent is built **without** a model — the model is injected at
        ``.run()`` time so Copilot token refresh is always current.
        """
        from pydantic_ai import Agent

        return Agent(system_prompt=self.get_system_prompt())

    def _get_agent(self) -> Agent:
        """Return the cached pydantic-ai Agent, building it on first call."""
        if self._pydantic_agent is None:
            self._pydantic_agent = self.build_pydantic_agent()
        return self._pydantic_agent

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_intent(task: dict[str, Any], fallback: str = "") -> str:
        """Return the natural-language intent from a task dict."""
        data = task.get("input_data", {})
        return data.get("intent") or task.get("title") or task.get("description", fallback)

    def can_handle(self, task: dict[str, Any]) -> bool:
        """Return True if this agent can handle the given task."""
        task_slug = task.get("agent_slug")
        if task_slug:
            return task_slug == self.slug
        # Fallback: check if any capability keyword is in task title
        title = task.get("title", "").lower()
        return any(cap.lower() in title for cap in self.capabilities)

    def get_system_prompt(self) -> str:
        return self.prompt_manager.compose_for_agent(
            self.slug, agent_instructions=self.instructions
        )

    async def ask_llm(
        self,
        prompt: str,
        system: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Send a free-form prompt to the LLM and return the text response.

        This helper is for pure text-generation tasks (e.g. drafting an
        email reply).  For tool-driven tasks use ``execute()`` which calls
        ``_get_agent().run()``.
        """
        from pydantic_ai import Agent

        from angie.llm import get_llm_model

        if system is None:
            system = self.get_system_prompt()

        try:
            model = get_llm_model()
            agent = Agent(system_prompt=system)
            result = await agent.run(prompt, model=model)
            return str(result.output)
        except Exception as exc:
            self.logger.error("LLM call failed: %s", exc)
            raise

    async def get_credentials(
        self, user_id: str | None, service_type: str
    ) -> dict[str, str] | None:
        """Load credentials from connections DB, fall back to None.

        Returns decrypted credential dict if a connection exists for the
        given *user_id* and *service_type*, otherwise ``None`` so the
        caller can fall back to env-var based configuration.
        """
        if not user_id:
            return None
        try:
            from angie.core.connections import get_connection
            from angie.core.crypto import decrypt_json

            conn = await get_connection(user_id, service_type)
            if conn and conn.credentials_encrypted:
                return decrypt_json(conn.credentials_encrypted)
        except Exception as exc:
            self.logger.debug("Connection lookup failed for %s/%s: %s", user_id, service_type, exc)
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} slug={self.slug!r}>"
