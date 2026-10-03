"""
tools.py

LangChain tool definitions for the travel planning agent.
Each tool wraps an existing service and exposes it to the agent
as a callable with a clear name, description, and typed input.

The agent reads tool names and descriptions to decide which ones
to call, so descriptions must be specific and action-oriented.
"""

import httpx
from fastapi import HTTPException
from langchain_core.tools import tool
from app.services.weather_service import get_weather_summary
from app.services.knowledge_service import search_knowledge
from app.database import session_factory
from app.models.trip import Trip
from app.config import settings

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


@tool
async def get_weather(destination: str) -> str:
    """Get the current weather forecast for a travel destination.

    Use this tool when the user wants weather-appropriate activity
    suggestions or asks about conditions at their destination.

    Args:
        destination: The name of the city or place to get weather for.

    Returns:
        A plain-English weather summary including temperature range
        and general conditions (sunny, mixed, rainy).
    """
    try:
        return await get_weather_summary(destination)
    except HTTPException:
        return f"Weather data unavailable for {destination}"
    except Exception:
        return "Weather service temporarily unavailable"


@tool
async def search_travel_knowledge(destination: str, query: str) -> str:
    """Search the travel knowledge base for destination-specific tips.

    Use this tool to retrieve local tips, hidden gems, food recommendations,
    budget advice, and transport information for a destination.

    Args:
        destination: The destination to search knowledge for.
        query: A specific aspect to search for, e.g. 'hidden gems',
               'budget tips', 'local food', 'transport'.

    Returns:
        Relevant travel knowledge chunks as a single string, or a message
        indicating no knowledge was found for that destination.
    """
    try:
        result = await search_knowledge(destination, query)
    except Exception:
        return "Knowledge base temporarily unavailable"

    if not result:
        return f"No knowledge found for {destination}"
    return result


@tool
def get_trip_details(trip_id: int, db_session: str) -> str:
    """Get the details of a trip from the database by its ID.

    Use this tool to retrieve the destination, number of days, budget,
    and travel style for a trip before generating an itinerary.

    Args:
        trip_id: The ID of the trip to retrieve.
        db_session: Not used directly, trip lookup is handled internally.

    Returns:
        A plain-English summary of the trip details, or an error message
        if the trip is not found.
    """
    db = session_factory()
    try:
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return f"Trip {trip_id} not found"
        return (
            f"Trip {trip_id}: {trip.days}-day trip to {trip.destination}, "
            f"budget ${trip.budget:.2f}, style: {trip.trip_style}"
        )
    finally:
        db.close()


@tool
async def get_place_info(destination: str, place_type: str) -> str:
    """Look up information about places of a specific type at a destination.

    Use this tool to find museums, restaurants, parks, landmarks, or
    other points of interest at the destination.

    Args:
        destination: The city or area to search in.
        place_type: The type of place to look for, e.g. 'museums',
                    'restaurants', 'parks', 'landmarks'.

    Returns:
        A plain-English description of relevant places found, or a
        message if none were found.
    """
    try:
        # Nominatim is a text-based search, so no coordinates are needed here
        params = {"q": f"{place_type} in {destination}", "format": "json", "limit": 5}
        headers = {"User-Agent": "ai-vacation-planner/1.0"}

        async with httpx.AsyncClient(timeout=settings.weather_api_timeout) as client:
            response = await client.get(NOMINATIM_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()

        if not results:
            return f"Could not find {place_type} information for {destination}"

        names = [place.get("display_name", "") for place in results if place.get("display_name")]
        return f"Found {place_type} in {destination}: " + "; ".join(names)
    except Exception:
        return f"Could not find {place_type} information for {destination}"


# All tools available to the agent
AGENT_TOOLS = [get_weather, search_travel_knowledge, get_trip_details, get_place_info]
