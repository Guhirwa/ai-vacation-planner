"""Weather lookup service backed by the free Open-Meteo API.

Provides destination geocoding and a short 7-day forecast summary, used to
give the LLM itinerary-generation prompt weather-aware context. Open-Meteo's
geocoding and forecast endpoints are public and require no API key.
"""

import httpx
from fastapi import HTTPException
from app.config import settings

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def get_coordinates(destination: str) -> tuple[float, float]:
    """Fetch the latitude and longitude for a destination using the
    Open-Meteo geocoding API.

    Args:
        destination: The name of the destination city or place.

    Returns:
        A tuple of (latitude, longitude).

    Raises:
        HTTPException(502): If the geocoding API call fails or the
            destination cannot be found.
    """
    params = {"name": destination, "count": 1, "language": "en", "format": "json"}

    try:
        async with httpx.AsyncClient(timeout=settings.weather_api_timeout) as client:
            response = await client.get(GEOCODING_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Weather geocoding lookup failed for '{destination}': {e}",
        )

    results = data.get("results")
    if not results:
        raise HTTPException(
            status_code=502,
            detail=f"Could not find coordinates for destination '{destination}'",
        )

    first_match = results[0]
    return float(first_match["latitude"]), float(first_match["longitude"])


async def get_weather_summary(destination: str) -> str:
    """Fetch a short weather summary for the destination using the
    Open-Meteo forecast API.

    Calls get_coordinates() first to resolve the destination to lat/lng,
    then fetches the 7-day forecast and summarises it as a plain-English
    string suitable for injecting into the LLM prompt.

    Args:
        destination: The name of the destination city or place.

    Returns:
        A plain-English weather summary string, for example:
        "Weather in Tokyo: highs around 28.4°C, lows around 21.1°C, sunny
        conditions expected."

    Raises:
        HTTPException(502): If either the geocoding or forecast API call fails.
    """
    latitude, longitude = await get_coordinates(destination)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "forecast_days": 7,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.weather_api_timeout) as client:
            response = await client.get(FORECAST_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Weather forecast lookup failed for '{destination}': {e}",
        )

    daily = data.get("daily", {})
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precipitation = daily.get("precipitation_sum") or []

    if not highs or not lows:
        raise HTTPException(
            status_code=502,
            detail=f"Weather forecast response for '{destination}' was incomplete",
        )

    avg_max = round(sum(highs) / len(highs), 1)
    avg_min = round(sum(lows) / len(lows), 1)
    total_precipitation = sum(precipitation)

    if total_precipitation < 5:
        condition = "sunny"
    elif total_precipitation > 30:
        condition = "rainy"
    else:
        condition = "mixed"

    return (
        f"Weather in {destination}: highs around {avg_max}°C, lows around "
        f"{avg_min}°C, {condition} conditions expected."
    )
