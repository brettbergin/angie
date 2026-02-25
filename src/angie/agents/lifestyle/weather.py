"""Weather agent — current conditions, forecasts, and severe weather alerts."""

from __future__ import annotations

import logging
import os
from typing import Any, ClassVar

import httpx
from pydantic_ai import RunContext

from angie.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_OWM_BASE = "https://api.openweathermap.org"


class WeatherAgent(BaseAgent):
    name: ClassVar[str] = "WeatherAgent"
    slug: ClassVar[str] = "weather"
    category: ClassVar[str] = "Lifestyle Agents"
    description: ClassVar[str] = "Weather conditions, forecasts, and severe weather alerts."
    capabilities: ClassVar[list[str]] = [
        "weather",
        "forecast",
        "temperature",
        "rain",
        "snow",
        "wind",
        "outfit",
        "alerts",
    ]
    instructions: ClassVar[str] = (
        "You provide weather information using the OpenWeatherMap API.\n\n"
        "Available tools:\n"
        "- get_current_weather: Current conditions for a location.\n"
        "- get_forecast: Multi-day forecast (up to 5 days).\n"
        "- get_alerts: Severe weather alerts for a location (requires One Call API subscription).\n\n"
        "When reporting weather:\n"
        "- Always include temperature, conditions, humidity, and wind.\n"
        "- Suggest appropriate clothing/outfit based on conditions.\n"
        "- Mention any precipitation probability.\n"
        "- Use natural, conversational language.\n"
        "- If the user doesn't specify units, default to metric (Celsius).\n"
    )

    def build_pydantic_agent(self):
        from pydantic_ai import Agent

        agent: Agent[dict[str, Any], str] = Agent(
            deps_type=dict,
            system_prompt=self.get_system_prompt(),
        )

        @agent.tool
        async def get_current_weather(
            ctx: RunContext[dict[str, Any]],
            location: str,
            units: str = "metric",
        ) -> dict[str, Any]:
            """Get current weather conditions for a location.

            Args:
                location: City name (e.g. "Toronto", "London,UK", "New York,US").
                units: Temperature units — "metric" (Celsius), "imperial" (Fahrenheit),
                       or "standard" (Kelvin). Defaults to metric.
            """
            api_key = ctx.deps["api_key"]
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_OWM_BASE}/data/2.5/weather",
                    params={"q": location, "appid": api_key, "units": units},
                )
                if resp.status_code != 200:
                    return {"error": f"Weather API returned HTTP {resp.status_code}"}
                data = resp.json()

            unit_label = {"metric": "°C", "imperial": "°F", "standard": "K"}.get(units, "°C")
            main = data.get("main", {})
            wind = data.get("wind", {})
            weather = data.get("weather", [{}])[0]

            return {
                "location": data.get("name", location),
                "country": data.get("sys", {}).get("country", ""),
                "description": weather.get("description", ""),
                "temperature": f"{main.get('temp', 'N/A')}{unit_label}",
                "feels_like": f"{main.get('feels_like', 'N/A')}{unit_label}",
                "temp_min": f"{main.get('temp_min', 'N/A')}{unit_label}",
                "temp_max": f"{main.get('temp_max', 'N/A')}{unit_label}",
                "humidity": f"{main.get('humidity', 'N/A')}%",
                "wind_speed": f"{wind.get('speed', 'N/A')} {'m/s' if units == 'metric' else 'mph'}",
                "clouds": f"{data.get('clouds', {}).get('all', 'N/A')}%",
                "visibility": f"{data.get('visibility', 'N/A')} m",
            }

        @agent.tool
        async def get_forecast(
            ctx: RunContext[dict[str, Any]],
            location: str,
            days: int = 3,
            units: str = "metric",
        ) -> dict[str, Any]:
            """Get a multi-day weather forecast for a location.

            Args:
                location: City name (e.g. "Toronto", "London,UK").
                days: Number of days to forecast (1-5). Defaults to 3.
                units: Temperature units — "metric", "imperial", or "standard".
            """
            api_key = ctx.deps["api_key"]
            days = max(1, min(5, days))

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_OWM_BASE}/data/2.5/forecast",
                    params={"q": location, "appid": api_key, "units": units},
                )
                if resp.status_code != 200:
                    return {"error": f"Weather API returned HTTP {resp.status_code}"}
                data = resp.json()

            unit_label = {"metric": "°C", "imperial": "°F", "standard": "K"}.get(units, "°C")
            forecasts: list[dict[str, Any]] = data.get("list", [])

            # Group 3-hour intervals into daily summaries
            daily: dict[str, dict[str, Any]] = {}
            for entry in forecasts:
                date = entry["dt_txt"].split(" ")[0]
                if date not in daily:
                    daily[date] = {
                        "date": date,
                        "temps": [],
                        "descriptions": [],
                        "humidity": [],
                        "wind_speeds": [],
                        "pop": [],
                    }
                main = entry.get("main", {})
                weather = entry.get("weather", [{}])[0]
                daily[date]["temps"].append(main.get("temp", 0))
                daily[date]["descriptions"].append(weather.get("description", ""))
                daily[date]["humidity"].append(main.get("humidity", 0))
                daily[date]["wind_speeds"].append(entry.get("wind", {}).get("speed", 0))
                daily[date]["pop"].append(entry.get("pop", 0))

            result_days = []
            for date_key in sorted(daily.keys())[:days]:
                d = daily[date_key]
                temps = d["temps"]
                # Pick the most common weather description for the day
                desc_counts: dict[str, int] = {}
                for desc in d["descriptions"]:
                    desc_counts[desc] = desc_counts.get(desc, 0) + 1
                primary_desc = max(desc_counts, key=desc_counts.get) if desc_counts else ""

                result_days.append(
                    {
                        "date": d["date"],
                        "temp_high": f"{max(temps):.1f}{unit_label}",
                        "temp_low": f"{min(temps):.1f}{unit_label}",
                        "description": primary_desc,
                        "avg_humidity": f"{(sum(d['humidity']) / len(d['humidity'])) if d['humidity'] else 0:.0f}%",
                        "max_wind": f"{max(d['wind_speeds']):.1f} {'m/s' if units == 'metric' else 'mph'}",
                        "precipitation_chance": f"{max(d['pop']) * 100:.0f}%",
                    }
                )

            city_info = data.get("city", {})
            return {
                "location": city_info.get("name", location),
                "country": city_info.get("country", ""),
                "days": result_days,
            }

        @agent.tool
        async def get_alerts(
            ctx: RunContext[dict[str, Any]],
            location: str,
        ) -> dict[str, Any]:
            """Get severe weather alerts for a location.

            This uses the OpenWeatherMap One Call API 3.0 which requires a subscription.
            Falls back to a basic check from current weather data if unavailable.

            Args:
                location: City name (e.g. "Toronto", "London,UK").
            """
            api_key = ctx.deps["api_key"]

            # First geocode the location to get lat/lon
            async with httpx.AsyncClient(timeout=10.0) as client:
                geo_resp = await client.get(
                    f"{_OWM_BASE}/geo/1.0/direct",
                    params={"q": location, "limit": 1, "appid": api_key},
                )
                geo_data = geo_resp.json()
                if geo_resp.status_code != 200 or not geo_data:
                    return {"error": f"Could not geocode location: {location}"}
                geo = geo_data[0]
                lat, lon = geo["lat"], geo["lon"]

                # Try One Call API for alerts
                resp = await client.get(
                    f"{_OWM_BASE}/data/3.0/onecall",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "appid": api_key,
                        "exclude": "minutely,hourly,daily",
                    },
                )

            if resp.status_code == 200:
                data = resp.json()
                alerts = data.get("alerts", [])
                if not alerts:
                    return {
                        "location": geo.get("name", location),
                        "alerts": [],
                        "message": "No active weather alerts for this location.",
                    }
                return {
                    "location": geo.get("name", location),
                    "alerts": [
                        {
                            "event": a.get("event", "Unknown"),
                            "sender": a.get("sender_name", ""),
                            "description": a.get("description", ""),
                            "start": a.get("start"),
                            "end": a.get("end"),
                        }
                        for a in alerts
                    ],
                }

            # Fallback: One Call API not available (401/402 = no subscription)
            return {
                "location": geo.get("name", location),
                "alerts": [],
                "message": (
                    "Weather alerts require an OpenWeatherMap One Call API 3.0 subscription. "
                    "No alerts data available. Use get_current_weather to check current conditions."
                ),
            }

        return agent

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        self.logger.info("WeatherAgent executing")
        try:
            user_id = task.get("user_id")
            creds = await self.get_credentials(user_id, "openweathermap")
            api_key = (creds or {}).get("api_key") or os.environ.get("OPENWEATHERMAP_API_KEY", "")

            if not api_key:
                return {
                    "summary": (
                        "No OpenWeatherMap API key configured. "
                        "Add your API key in Settings → Connections → OpenWeatherMap."
                    ),
                    "error": "No API key configured",
                }

            from angie.llm import get_llm_model

            intent = self._extract_intent(task, fallback="what's the weather like?")
            deps: dict[str, Any] = {"api_key": api_key}
            result = await self._get_agent().run(intent, model=get_llm_model(), deps=deps)
            return {"summary": str(result.output)}

        except Exception as exc:  # noqa: BLE001
            self.logger.exception("WeatherAgent error")
            return {"summary": f"Weather error: {exc}", "error": str(exc)}
