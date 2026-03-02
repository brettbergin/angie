"""BaseAgent — pydantic-ai agent wrapper with pluggable LLM backend."""

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
    - An external service SDK (GitHub, Slack, etc.)
    - A pydantic-ai Agent whose @tool functions call the SDK
    - A pluggable LLM backend (GitHub Models, OpenAI, or Anthropic)

    The LLM decides which tool(s) to invoke based on a natural-language
    *intent* extracted from the incoming task.  The pydantic-ai model is
    injected at `agent.run()` time (never stored on the Agent instance)
    so that token refreshes are always picked up automatically.
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
        ``.run()`` time so the configured LLM provider is always current.
        """
        from pydantic_ai import Agent

        return Agent(system_prompt=self.get_system_prompt())

    def _get_agent(self) -> Agent:
        """Return the cached pydantic-ai Agent, building it on first call."""
        if self._pydantic_agent is None:
            self._pydantic_agent = self.build_pydantic_agent()
        return self._pydantic_agent

    # ------------------------------------------------------------------
    # Run with token tracking
    # ------------------------------------------------------------------

    async def _run_with_tracking(
        self,
        prompt: str,
        *,
        model: Any = None,
        deps: Any = None,
        user_id: str | None = None,
        task_id: str | None = None,
        conversation_id: str | None = None,
    ) -> Any:
        """Run the pydantic-ai agent and record token usage.

        Returns the full AgentRunResult so callers can extract ``.output``.
        """
        from angie.core.token_usage import record_usage_fire_and_forget

        kwargs: dict[str, Any] = {"model": model}
        if deps is not None:
            kwargs["deps"] = deps

        result = await self._get_agent().run(prompt, **kwargs)

        record_usage_fire_and_forget(
            user_id=user_id,
            agent_slug=self.slug,
            usage=result.usage(),
            source="agent_execute",
            task_id=task_id,
            conversation_id=conversation_id,
        )

        return result

    # ------------------------------------------------------------------
    # Confidence scoring (for smart routing)
    # ------------------------------------------------------------------

    def confidence(self, task: dict[str, Any]) -> float:
        """Return 0.0-1.0 confidence that this agent can handle the task.

        Default: keyword matching with scoring.
        Subclasses can override for custom logic.
        """
        task_slug = task.get("agent_slug")
        if task_slug and task_slug == self.slug:
            return 1.0  # Explicit match
        if task_slug:
            return 0.0  # Different agent explicitly requested

        title = task.get("title", "").lower()
        text = task.get("input_data", {}).get("text", "").lower()
        combined = f"{title} {text}"

        if not self.capabilities:
            return 0.0

        matches = sum(1 for cap in self.capabilities if cap.lower() in combined)
        return min(matches / len(self.capabilities), 1.0) * 0.8  # Cap at 0.8 for keyword

    # ------------------------------------------------------------------
    # Autonomous capabilities
    # ------------------------------------------------------------------

    async def notify_user(
        self, user_id: str, message: str, channel: str | None = None, **kwargs: Any
    ) -> None:
        """Send a proactive notification to a user via their preferred channel."""
        from angie.core.feedback import get_feedback

        await get_feedback().send_mention(user_id, message, channel=channel, **kwargs)

    async def schedule_followup(
        self,
        *,
        user_id: str,
        delay_seconds: int,
        title: str,
        intent: str,
        agent_slug: str | None = None,
        conversation_id: str | None = None,
    ) -> str | None:
        """Schedule a follow-up task to run after a delay.

        Creates a one-shot scheduled job in the DB that fires after delay_seconds.
        Returns the scheduled job ID on success, or ``None`` if the DB write failed.
        """
        import uuid
        from datetime import UTC, datetime, timedelta

        from angie.db.session import get_session_factory
        from angie.models.schedule import ScheduledJob

        job_id = str(uuid.uuid4())
        run_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)

        try:
            async with get_session_factory()() as session:
                job = ScheduledJob(
                    id=job_id,
                    user_id=user_id,
                    name=title,
                    description=f"Follow-up: {intent}",
                    cron_expression="@once",
                    agent_slug=agent_slug or self.slug,
                    task_payload={"intent": intent, "title": title},
                    is_enabled=True,
                    next_run_at=run_at,
                    conversation_id=conversation_id,
                )
                session.add(job)
                await session.commit()
            self.logger.info("Scheduled follow-up %s in %ds", job_id, delay_seconds)
            return job_id
        except Exception as exc:
            self.logger.warning("Failed to schedule follow-up: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Auto-notify / should_respond
    # ------------------------------------------------------------------

    async def should_respond(self, task: dict[str, Any]) -> bool:
        """Decide whether this agent should respond to an auto_notify task.

        Evaluates relevance by checking if the user's latest message
        contains keywords that match this agent's ``capabilities``.
        Returns False if the message is unrelated to this agent's domain.

        Subclasses can override for custom relevance logic.
        """
        params = task.get("input_data", {}).get("parameters", {})
        if not params.get("auto_notify"):
            return False

        if not self.capabilities:
            return False

        # Extract the user message text to evaluate relevance
        intent = self._extract_intent(task)
        if not intent:
            return False

        text = intent.lower()

        # Check if any capability keyword appears in the message
        for cap in self.capabilities:
            if cap.lower() in text:
                return True

        # Check conversation history for recent context relevance
        conversation_id = task.get("input_data", {}).get("conversation_id")
        if conversation_id:
            history = await self.get_conversation_history(conversation_id, limit=5)
            # Check the last few USER messages for capability relevance
            recent_user_msgs = [
                m["content"].lower()
                for m in history
                if m.get("role") == "USER" or m.get("role") == "user"
            ]
            # Only check the 2 most recent user messages
            for msg_text in recent_user_msgs[-2:]:
                for cap in self.capabilities:
                    if cap.lower() in msg_text:
                        return True

        return False

    # ------------------------------------------------------------------
    # Conversation context
    # ------------------------------------------------------------------

    async def get_conversation_history(
        self, conversation_id: str, limit: int = 20
    ) -> list[dict[str, str]]:
        """Query recent messages from a conversation for context.

        Returns a list of dicts with ``role``, ``content``, and ``agent_slug`` keys,
        ordered by creation time (oldest first).
        """
        try:
            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.conversation import ChatMessage

            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.conversation_id == conversation_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(limit)
                )
                # Fetch newest-first so LIMIT keeps recent messages,
                # then reverse to return them in chronological (oldest→newest) order.
                messages = list(reversed(result.scalars().all()))
                return [
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                        "agent_slug": msg.agent_slug or "",
                    }
                    for msg in messages
                ]
        except Exception as exc:
            self.logger.warning("Failed to load conversation history: %s", exc)
            return []

    def _build_context_prompt(self, intent: str, history: list[dict[str, str]]) -> str:
        """Format conversation history + intent into a context-enriched prompt.

        If history is empty, returns the raw intent unchanged.
        """
        if not history:
            return intent

        lines = ["## Conversation Context"]
        for msg in history:
            role = msg.get("role", "user")
            agent = msg.get("agent_slug", "")
            if role == "user":
                label = "USER"
            elif agent:
                label = agent
            else:
                label = "ASSISTANT"
            lines.append(f"[{label}]: {msg['content']}")

        lines.append("---")
        lines.append("## Your Task")
        lines.append(intent)
        return "\n".join(lines)

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
            from angie.core.token_usage import record_usage_fire_and_forget

            model = get_llm_model()
            agent = Agent(system_prompt=system)
            result = await agent.run(prompt, model=model)
            record_usage_fire_and_forget(
                user_id=user_id,
                agent_slug=self.slug,
                usage=result.usage(),
                source="ask_llm",
            )
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
