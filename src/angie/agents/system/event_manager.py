"""Event manager agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class EventManagerAgent(BaseAgent):
    name: ClassVar[str] = "Event Manager"
    slug: ClassVar[str] = "event-manager"
    description: ClassVar[str] = "Query, filter, and manage Angie events."
    capabilities: ClassVar[list[str]] = ["event", "list events", "event history"]

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[None, str] = Agent(system_prompt=self.get_system_prompt())

        @agent.tool_plain
        async def list_events(event_type: str = "", limit: int = 20) -> dict:
            """List recent Angie events, optionally filtered by type."""
            from sqlalchemy import select

            from angie.db.session import get_session_factory
            from angie.models.event import Event, EventType

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(Event).order_by(Event.created_at.desc()).limit(limit)
                if event_type:
                    try:
                        stmt = stmt.where(Event.type == EventType(event_type))
                    except ValueError:
                        return {"error": f"Invalid event type: {event_type}"}
                result = await session.execute(stmt)
                events = result.scalars().all()
                return {
                    "events": [
                        {
                            "id": e.id,
                            "type": e.type.value,
                            "source_channel": e.source_channel,
                            "processed": e.processed,
                            "created_at": str(e.created_at),
                        }
                        for e in events
                    ]
                }

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        from angie.llm import get_llm_model

        intent = self._extract_intent(task, fallback="list events")
        self.logger.info("EventManagerAgent intent=%r", intent)
        try:
            result = await self._get_agent().run(intent, model=get_llm_model())
            return {"result": str(result.output)}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("EventManagerAgent error")
            return {"error": str(exc)}
