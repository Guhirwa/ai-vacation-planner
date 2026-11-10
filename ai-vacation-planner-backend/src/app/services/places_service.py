"""
places_service.py

Looks up points of interest at a destination using the free Nominatim
(OpenStreetMap) search API.

This is the one place that actually calls Nominatim. It used to be
implemented three separate times (the agent tool, the REST MCP client, and
the stdio MCP server), each with no retry, so a single slow response from
this free, unauthenticated API failed the whole call outright instead of
being retried.
"""

import asyncio
import logging

import httpx

from app.config import settings
from app.guardrails.input_guardrails import validate_search_term

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
PLACE_SEARCH_RETRIES = 2
PLACE_SEARCH_RETRY_DELAY_SECONDS = 1


async def search_places(destination: str, place_type: str) -> list[str]:
    """Search Nominatim for places of a given type at a destination.

    Validates both inputs before building the query, and retries on a
    timeout or connection error, since a single slow response from this
    free API shouldn't fail the whole lookup.

    Args:
        destination: The city or area to search in.
        place_type: The type of place to look for, e.g. 'museums'.

    Returns:
        The display names of the matched places. Empty if none were
        found or the lookup failed after retrying.

    Raises:
        InvalidSearchTerm: If destination or place_type contains
            characters or length not allowed in a search term.
    """
    validate_search_term(destination, "destination")
    validate_search_term(place_type, "place_type")

    params = {"q": f"{place_type} in {destination}", "format": "json", "limit": 5}
    headers = {"User-Agent": "ai-vacation-planner/1.0"}

    last_error: Exception | None = None
    for attempt in range(1, PLACE_SEARCH_RETRIES + 2):
        try:
            async with httpx.AsyncClient(timeout=settings.weather_api_timeout) as client:
                response = await client.get(NOMINATIM_SEARCH_URL, params=params, headers=headers)
                response.raise_for_status()
                results = response.json()
            return [place.get("display_name", "") for place in results if place.get("display_name")]
        except Exception as e:
            last_error = e
            logger.warning(
                "Place search attempt %d/%d failed for %r in %r: %s",
                attempt, PLACE_SEARCH_RETRIES + 1, place_type, destination, str(e),
            )
            if attempt <= PLACE_SEARCH_RETRIES:
                await asyncio.sleep(PLACE_SEARCH_RETRY_DELAY_SECONDS)

    logger.error(
        "Place search failed after %d attempts for %r in %r: %s",
        PLACE_SEARCH_RETRIES + 1, place_type, destination, str(last_error),
    )
    return []
