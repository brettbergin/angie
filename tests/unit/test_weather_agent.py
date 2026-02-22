"""Unit tests for the WeatherAgent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from angie.agents.lifestyle.weather import WeatherAgent

# ── WeatherAgent basics ──────────────────────────────────────────────


def test_weather_agent_attributes():
    agent = WeatherAgent()
    assert agent.slug == "weather"
    assert agent.category == "Lifestyle Agents"
    assert "weather" in agent.capabilities
    assert "forecast" in agent.capabilities


def test_weather_agent_build_pydantic_agent():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool_names = list(pa._function_toolset.tools.keys())
    assert "get_current_weather" in tool_names
    assert "get_forecast" in tool_names
    assert "get_alerts" in tool_names


# ── get_current_weather tool ─────────────────────────────────────────


@pytest.mark.anyio
async def test_get_current_weather_success():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_current_weather"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Toronto",
        "sys": {"country": "CA"},
        "main": {
            "temp": 22.5,
            "feels_like": 21.0,
            "temp_min": 20.0,
            "temp_max": 25.0,
            "humidity": 65,
        },
        "wind": {"speed": 3.5},
        "weather": [{"description": "clear sky"}],
        "clouds": {"all": 10},
        "visibility": 10000,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto")

    assert result["location"] == "Toronto"
    assert result["country"] == "CA"
    assert "22.5" in result["temperature"]
    assert result["description"] == "clear sky"
    assert "65%" in result["humidity"]


@pytest.mark.anyio
async def test_get_current_weather_api_error():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_current_weather"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid API key"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto")

    assert "error" in result
    assert "401" in result["error"]


# ── get_forecast tool ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_get_forecast_success():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_forecast"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "city": {"name": "Toronto", "country": "CA"},
        "list": [
            {
                "dt_txt": "2025-01-15 12:00:00",
                "main": {"temp": 5.0, "humidity": 70},
                "weather": [{"description": "light snow"}],
                "wind": {"speed": 4.0},
                "pop": 0.8,
            },
            {
                "dt_txt": "2025-01-15 15:00:00",
                "main": {"temp": 3.0, "humidity": 75},
                "weather": [{"description": "light snow"}],
                "wind": {"speed": 5.0},
                "pop": 0.6,
            },
            {
                "dt_txt": "2025-01-16 12:00:00",
                "main": {"temp": -2.0, "humidity": 60},
                "weather": [{"description": "clear sky"}],
                "wind": {"speed": 2.0},
                "pop": 0.1,
            },
        ],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto", days=2)

    assert result["location"] == "Toronto"
    assert len(result["days"]) == 2
    day1 = result["days"][0]
    assert day1["date"] == "2025-01-15"
    assert "5.0" in day1["temp_high"]
    assert "3.0" in day1["temp_low"]
    assert day1["description"] == "light snow"
    assert "80%" in day1["precipitation_chance"]


# ── get_alerts tool ──────────────────────────────────────────────────


@pytest.mark.anyio
async def test_get_alerts_no_alerts():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_alerts"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_geo_response = MagicMock()
    mock_geo_response.status_code = 200
    mock_geo_response.json.return_value = [{"name": "Toronto", "lat": 43.65, "lon": -79.38}]

    mock_onecall_response = MagicMock()
    mock_onecall_response.status_code = 200
    mock_onecall_response.json.return_value = {"alerts": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_geo_response, mock_onecall_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto")

    assert result["location"] == "Toronto"
    assert result["alerts"] == []
    assert "No active" in result["message"]


@pytest.mark.anyio
async def test_get_alerts_with_alert():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_alerts"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_geo_response = MagicMock()
    mock_geo_response.status_code = 200
    mock_geo_response.json.return_value = [{"name": "Toronto", "lat": 43.65, "lon": -79.38}]

    mock_onecall_response = MagicMock()
    mock_onecall_response.status_code = 200
    mock_onecall_response.json.return_value = {
        "alerts": [
            {
                "event": "Winter Storm Warning",
                "sender_name": "Environment Canada",
                "description": "Heavy snow expected",
                "start": 1700000000,
                "end": 1700100000,
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_geo_response, mock_onecall_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto")

    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["event"] == "Winter Storm Warning"


@pytest.mark.anyio
async def test_get_alerts_fallback_no_subscription():
    agent = WeatherAgent()
    pa = agent.build_pydantic_agent()
    tool = pa._function_toolset.tools["get_alerts"]

    mock_ctx = MagicMock()
    mock_ctx.deps = {"api_key": "test-key"}

    mock_geo_response = MagicMock()
    mock_geo_response.status_code = 200
    mock_geo_response.json.return_value = [{"name": "Toronto", "lat": 43.65, "lon": -79.38}]

    mock_onecall_response = MagicMock()
    mock_onecall_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_geo_response, mock_onecall_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("angie.agents.lifestyle.weather.httpx.AsyncClient", return_value=mock_client):
        result = await tool.function(mock_ctx, location="Toronto")

    assert result["alerts"] == []
    assert "subscription" in result["message"].lower()


# ── execute method ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_execute_no_api_key():
    agent = WeatherAgent()
    with patch.object(agent, "get_credentials", new_callable=AsyncMock, return_value=None):
        with patch.dict("os.environ", {}, clear=True):
            result = await agent.execute({"user_id": "u1", "input_data": {"intent": "weather"}})

    assert "error" in result
    assert "API key" in result["summary"]


@pytest.mark.anyio
async def test_execute_with_credentials():
    agent = WeatherAgent()
    mock_run = AsyncMock()
    mock_run.return_value.output = "It's 22°C and sunny in Toronto."

    with (
        patch.object(
            agent, "get_credentials", new_callable=AsyncMock, return_value={"api_key": "k"}
        ),
        patch.object(agent, "_get_agent") as mock_agent,
        patch("angie.llm.get_llm_model", return_value="test-model"),
    ):
        mock_agent.return_value.run = mock_run
        result = await agent.execute(
            {
                "user_id": "u1",
                "input_data": {"intent": "weather in Toronto"},
            }
        )

    assert result["summary"] == "It's 22°C and sunny in Toronto."
