"""cleo-mcp-weather — a one-line local weather read for the cover. No key.

Wraps the free Open-Meteo API. Set your coordinates in the source block:

    [[sources]]
    beat   = "weather"
    server = "weather"
    tool   = "today"
    args   = { lat = 12.97, lon = 77.59, place = "Bangalore" }

Run standalone:   python -m servers.weather.server
"""

from __future__ import annotations

import json

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cleo-weather")

_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "violent showers",
    95: "thunderstorm", 96: "thunderstorm + hail", 99: "thunderstorm + hail",
}


@mcp.tool()
def today(lat: float, lon: float, place: str = "") -> str:
    """Return one Item-shaped weather line for `place` at (lat, lon)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&timezone=auto&forecast_days=1"
    )
    r = httpx.get(url, timeout=15.0)
    r.raise_for_status()
    d = r.json()["daily"]
    hi, lo = round(d["temperature_2m_max"][0]), round(d["temperature_2m_min"][0])
    cond = _CODES.get(d["weather_code"][0], "—")
    where = f" in {place}" if place else ""
    line = f"{cond}{where}, {lo}–{hi}°C"
    item = {
        "id": f"weather-{d['time'][0]}",
        "beat": "weather",
        "source": "Open-Meteo",
        "title": line,
        "text": line,
        "raw": {"hi": hi, "lo": lo, "code": d["weather_code"][0], "place": place},
    }
    return json.dumps({"items": [item]}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
