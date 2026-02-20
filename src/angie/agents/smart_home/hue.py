"""Philips Hue smart lighting control agent."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from angie.agents.base import BaseAgent


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

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("input_data", {}).get("action", "list")
        self.logger.info("HueAgent action=%s", action)
        try:
            from phue import Bridge

            bridge_ip = os.environ.get("HUE_BRIDGE_IP", "")
            if not bridge_ip:
                return {"error": "HUE_BRIDGE_IP not configured"}
            bridge = Bridge(bridge_ip)
            bridge.connect()
            return self._dispatch(bridge, action, task.get("input_data", {}))
        except ImportError:
            return {"error": "phue not installed"}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("HueAgent error")
            return {"error": str(exc)}

    def _dispatch(self, bridge: Any, action: str, data: dict[str, Any]) -> dict[str, Any]:
        if action == "list":
            lights = bridge.get_light_objects("name")
            return {"lights": [{"name": n, "on": light.on} for n, light in lights.items()]}

        if action == "on":
            name = data.get("light", "")
            if name:
                bridge.set_light(name, "on", True)
            else:
                bridge.set_group(0, "on", True)
            return {"on": True, "light": name or "all"}

        if action == "off":
            name = data.get("light", "")
            if name:
                bridge.set_light(name, "on", False)
            else:
                bridge.set_group(0, "on", False)
            return {"off": True, "light": name or "all"}

        if action == "brightness":
            name = data.get("light", "")
            bri = max(0, min(254, int(data.get("brightness", 127))))
            if name:
                bridge.set_light(name, "bri", bri)
            else:
                bridge.set_group(0, "bri", bri)
            return {"brightness": bri, "light": name or "all"}

        if action == "color":
            name = data.get("light", "")
            hue = int(data.get("hue", 0))  # 0-65535
            sat = int(data.get("saturation", 254))
            if name:
                bridge.set_light(name, {"hue": hue, "sat": sat})
            else:
                bridge.set_group(0, {"hue": hue, "sat": sat})
            return {"color_set": True, "hue": hue, "saturation": sat}

        return {"error": f"Unknown action: {action}"}
