"""Home Assistant smart home control agent — REST API."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


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

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "states")
        self.logger.info("HomeAssistantAgent action=%s", action)
        ha_url = os.environ.get("HOME_ASSISTANT_URL", "")
        ha_token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
        if not ha_url or not ha_token:
            return {"error": "HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN must be set"}
        try:
            import aiohttp

            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
            ) as session:
                return await self._dispatch(
                    session, ha_url.rstrip("/"), action, task.get("input_data", {})
                )
        except ImportError:
            return {"error": "aiohttp not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("HomeAssistantAgent error")
            return {"error": str(exc)}

    async def _dispatch(
        self, session: Any, base: str, action: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        if action == "states":
            async with session.get(f"{base}/api/states") as r:
                states = await r.json()
            return {"entities": [{"id": s["entity_id"], "state": s["state"]} for s in states[:50]]}

        if action == "get":
            entity_id = data.get("entity_id", "")
            async with session.get(f"{base}/api/states/{entity_id}") as r:
                return await r.json()

        if action == "call_service":
            domain = data.get("domain", "")
            service = data.get("service", "")
            entity_id = data.get("entity_id", "")
            payload = data.get("service_data", {"entity_id": entity_id} if entity_id else {})
            async with session.post(f"{base}/api/services/{domain}/{service}", json=payload) as r:
                result = await r.json()
            return {"called": True, "result": result}

        if action == "turn_on":
            entity_id = data.get("entity_id", "")
            async with session.post(
                f"{base}/api/services/homeassistant/turn_on", json={"entity_id": entity_id}
            ) as r:
                await r.json()
            return {"on": True, "entity_id": entity_id}

        if action == "turn_off":
            entity_id = data.get("entity_id", "")
            async with session.post(
                f"{base}/api/services/homeassistant/turn_off", json={"entity_id": entity_id}
            ) as r:
                await r.json()
            return {"off": True, "entity_id": entity_id}

        return {"error": f"Unknown action: {action}"}
