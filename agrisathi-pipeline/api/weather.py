"""
Live weather layer — OpenWeatherMap free tier.

GET /weather?district=Nagpur  returns current conditions for that district.
fetch_weather_data()          is also imported directly by advisor.py.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.config import OPENWEATHER_API_KEY
from core.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

_OWM_URL = (
    "https://api.openweathermap.org/data/2.5/weather"
    "?q={district},Maharashtra,IN&appid={key}&units=metric"
)


# ── Schema ────────────────────────────────────────────────────────────────────

class WeatherOut(BaseModel):
    district: str
    temp_c: float
    humidity: int
    description: str
    rainfall_mm: float


# ── Core fetch (shared with advisor.py) ───────────────────────────────────────

def fetch_weather_data(district: str) -> WeatherOut | None:
    """
    Call OpenWeatherMap and return a WeatherOut, or None if the key is missing
    or the request fails.  Never raises — callers handle None gracefully.
    """
    if not OPENWEATHER_API_KEY:
        log.debug("OPENWEATHER_API_KEY not set — skipping weather fetch.")
        return None

    url = _OWM_URL.format(district=district, key=OPENWEATHER_API_KEY)
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("Weather fetch failed for %r: %s", district, exc)
        return None

    data = resp.json()
    main    = data.get("main", {})
    weather = data.get("weather", [{}])[0]
    rain    = data.get("rain", {})

    return WeatherOut(
        district=district,
        temp_c=main.get("temp", 0.0),
        humidity=main.get("humidity", 0),
        description=weather.get("description", ""),
        rainfall_mm=rain.get("1h", rain.get("3h", 0.0)),
    )


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/weather", response_model=WeatherOut)
def get_weather(
    district: str = Query(..., description="Maharashtra district name, e.g. 'Nagpur'"),
):
    """Return current weather conditions for the given district."""
    if not OPENWEATHER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHER_API_KEY is not set. Add it to .env and restart.",
        )

    result = fetch_weather_data(district)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch weather for '{district}'. Check the district name.",
        )
    return result
