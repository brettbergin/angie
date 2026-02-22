"""Philips Hue smart lighting control agent."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

if TYPE_CHECKING:
    from pydantic_ai import Agent


class HueAgent(BaseAgent):
    name: ClassVar[str] = "HueAgent"
    slug: ClassVar[str] = "hue"
    description: ClassVar[str] = "Philips Hue smart lighting control."
    capabilities: ClassVar[list[str]] = [
        "lights",
        "hue",
        "brightness",
        "lighting",
        "turn on lights",
        "turn off lights",
        "color",
        "dim",
    ]
    instructions: ClassVar[str] = (
        "You control Philips Hue smart lights via the Hue Bridge.\n\n"
        "Available tools:\n"
        "- list_lights: List all lights with their current on/off state.\n"
        "- turn_on_light: Turn on a specific light by name, or all lights if no name given.\n"
        "- turn_off_light: Turn off a specific light by name, or all lights if no name given.\n"
        "- set_brightness: Set brightness (0-254) for a specific light or all lights.\n"
        "- set_color: Set color using hue (0-65535) and saturation (0-254) values.\n\n"
        "Requires HUE_BRIDGE_IP environment variable pointing to the Hue Bridge on the "
        "local network."
    )

    def build_pydantic_agent(self) -> Agent:
        from pydantic_ai import Agent

        agent: Agent[object, str] = Agent(
            deps_type=object,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        def list_lights(ctx: RunContext[object]) -> dict:
            """List all Philips Hue lights and their current on/off state."""
            bridge = ctx.deps
            lights = bridge.get_light_objects("name")
            return {"lights": [{"name": n, "on": light.on} for n, light in lights.items()]}

        @agent.tool
        def turn_on_light(ctx: RunContext[object], light_name: str = "") -> dict:
            """Turn on a specific Hue light by name, or all lights if no name given."""
            bridge = ctx.deps
            if light_name:
                bridge.set_light(light_name, "on", True)
            else:
                bridge.set_group(0, "on", True)
            return {"on": True, "light": light_name or "all"}

        @agent.tool
        def turn_off_light(ctx: RunContext[object], light_name: str = "") -> dict:
            """Turn off a specific Hue light by name, or all lights if no name given."""
            bridge = ctx.deps
            if light_name:
                bridge.set_light(light_name, "on", False)
            else:
                bridge.set_group(0, "on", False)
            return {"off": True, "light": light_name or "all"}

        @agent.tool
        def set_brightness(ctx: RunContext[object], brightness: int, light_name: str = "") -> dict:
            """Set the brightness of a Hue light (0-254), or all lights if no name given."""
            bridge = ctx.deps
            bri = max(0, min(254, brightness))
            if light_name:
                bridge.set_light(light_name, "bri", bri)
            else:
                bridge.set_group(0, "bri", bri)
            return {"brightness": bri, "light": light_name or "all"}

        @agent.tool
        def set_color(
            ctx: RunContext[object], hue: int, saturation: int, light_name: str = ""
        ) -> dict:
            """Set the color of a Hue light using hue (0-65535) and saturation (0-254)."""
            bridge = ctx.deps
            if light_name:
                bridge.set_light(light_name, {"hue": hue, "sat": saturation})
            else:
                bridge.set_group(0, {"hue": hue, "sat": saturation})
            return {"color_set": True, "hue": hue, "saturation": saturation}

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("HueAgent executing")
        try:
            from phue import Bridge

            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "hue")
            bridge_ip = (creds or {}).get("bridge_ip") or os.environ.get("HUE_BRIDGE_IP", "")
            if not bridge_ip:
                return {"error": "HUE_BRIDGE_IP not configured"}
            bridge = Bridge(bridge_ip)
            bridge.connect()
            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="list all lights")
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=bridge)
            return {"result": str(result.output)}
        except ImportError:
            return {"error": "phue not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("HueAgent error")
            return {"error": str(exc)}
