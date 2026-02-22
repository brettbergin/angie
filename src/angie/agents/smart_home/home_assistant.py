"""Home Assistant smart home control agent — REST API."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class HomeAssistantAgent(BaseAgent):
    name: ClassVar[str] = "HomeAssistantAgent"
    slug: ClassVar[str] = "home-assistant"
    description: ClassVar[str] = "Home Assistant smart home control."
    capabilities: ClassVar[list[str]] = [
        "home assistant",
        "smart home",
        "automation",
        "thermostat",
        "switch",
        "sensor",
        "entity",
    ]
    instructions: ClassVar[str] = (
        "You control a Home Assistant instance via its REST API.\n\n"
        "Available tools:\n"
        "- get_all_states: Get the current state of all entities (returns up to 50).\n"
        "- get_entity_state: Get the state of a specific entity by its entity_id "
        "(e.g. 'light.living_room', 'switch.fan', 'sensor.temperature').\n"
        "- turn_on_entity: Turn on any controllable entity (lights, switches, etc.).\n"
        "- turn_off_entity: Turn off any controllable entity.\n"
        "- call_service: Call any Home Assistant service by domain and service name "
        "(e.g. domain='climate', service='set_temperature').\n\n"
        "Requires HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN environment variables."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        # deps is a dict: {"url": str, "token": str}
        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        async def get_all_states(ctx: RunContext[object]) -> dict:
            """Get the current state of all Home Assistant entities."""
            import aiohttp

            config = ctx.deps
            headers = {
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{config['url']}/api/states") as r:
                    states = await r.json()
            return {"entities": [{"id": s["entity_id"], "state": s["state"]} for s in states[:50]]}

        @agent.tool
        async def get_entity_state(ctx: RunContext[object], entity_id: str) -> dict:
            """Get the current state of a specific Home Assistant entity."""
            import aiohttp

            config = ctx.deps
            headers = {
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{config['url']}/api/states/{entity_id}") as r:
                    return await r.json()

        @agent.tool
        async def turn_on_entity(ctx: RunContext[object], entity_id: str) -> dict:
            """Turn on a Home Assistant entity (light, switch, etc.)."""
            import aiohttp

            config = ctx.deps
            headers = {
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(
                    f"{config['url']}/api/services/homeassistant/turn_on",
                    json={"entity_id": entity_id},
                ) as r:
                    await r.json()
            return {"on": True, "entity_id": entity_id}

        @agent.tool
        async def turn_off_entity(ctx: RunContext[object], entity_id: str) -> dict:
            """Turn off a Home Assistant entity (light, switch, etc.)."""
            import aiohttp

            config = ctx.deps
            headers = {
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(
                    f"{config['url']}/api/services/homeassistant/turn_off",
                    json={"entity_id": entity_id},
                ) as r:
                    await r.json()
            return {"off": True, "entity_id": entity_id}

        @agent.tool
        async def call_service(
            ctx: RunContext[object],
            domain: str,
            service: str,
            entity_id: str = "",
        ) -> dict:
            """Call any Home Assistant service (domain/service)."""
            import aiohttp

            config = ctx.deps
            headers = {
                "Authorization": f"Bearer {config['token']}",
                "Content-Type": "application/json",
            }
            payload = {"entity_id": entity_id} if entity_id else {}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(
                    f"{config['url']}/api/services/{domain}/{service}", json=payload
                ) as r:
                    result = await r.json()
            return {"called": True, "result": result}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        user_id = task.get("user_id")
        creds = await self.get_credentials(user_id, "home_assistant")
        ha_url = (creds or {}).get("url") or os.environ.get("HOME_ASSISTANT_URL", "")
        ha_token = (creds or {}).get("token") or os.environ.get("HOME_ASSISTANT_TOKEN", "")
        if not ha_url or not ha_token:
            return {"error": "HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN must be set"}
        self.logger.info("HomeAssistantAgent executing")
        try:
            import aiohttp  # noqa: F401 — verify installed before proceeding

            from angie.llm import get_llm_model

            config = {"url": ha_url.rstrip("/"), "token": ha_token}
            intent = self._extract_intent(task, fallback="list all entity states")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=config)
            return {"result": str(result.output)}
        except ImportError:
            return {"error": "aiohttp not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("HomeAssistantAgent error")
            return {"error": str(exc)}
