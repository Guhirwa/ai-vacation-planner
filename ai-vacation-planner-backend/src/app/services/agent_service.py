"""
agent_service.py

Entry point for AI-powered itinerary generation using the LangGraph agent.

Replaces the direct LLM service call with an agent that decides at runtime
which tools to call (weather, knowledge, place lookup) before generating
the final itinerary. Validation is handled inside the agent graph itself.
"""

import logging
from fastapi import HTTPException
from app.agent.graph import run_agent
from app.schemas.itinerary import DayActivity

logger = logging.getLogger(__name__)


async def generate_itinerary_with_agent(
    trip_id: int,
    destination: str,
    days: int,
    budget: float,
    trip_style: str,
) -> list[DayActivity]:
    """Generate a travel itinerary using the LangGraph agent.

    Builds a plain-text request from the trip details and passes it to
    run_agent(), which orchestrates tool calls and validates the response
    against LLMItineraryOutput before returning. The validated result is
    converted to a list of DayActivity objects for the router to persist.

    Args:
        trip_id: The database ID of the trip, passed to the agent so it
                 can use the get_trip_details tool to look up the full record.
        destination: The travel destination.
        days: Number of days the trip lasts.
        budget: Total trip budget in USD.
        trip_style: One of the allowed trip styles.

    Returns:
        A list of DayActivity objects, one per day, each with a day number
        and a list of 3 to 5 activities.

    Raises:
        HTTPException(500): If the agent fails to produce a valid itinerary
                            after all retry attempts.
    """
    request = (
        f"Plan a {days}-day trip to {destination} for trip ID {trip_id}. "
        f"Budget: ${budget:.2f} USD. Travel style: {trip_style}. "
        f"Use the available tools to gather weather, local knowledge, and place "
        f"information before generating the itinerary."
    )

    logger.info("Starting agent itinerary generation for trip %d (%s)", trip_id, destination)

    try:
        result = await run_agent(request)
        days_list = [DayActivity(day=d["day"], activities=d["activities"]) for d in result["days"]]
        logger.info("Agent generated %d days for trip %d", len(days_list), trip_id)
        return days_list
    except ValueError as e:
        logger.error("Agent failed for trip %d: %s", trip_id, str(e))
        raise HTTPException(status_code=500, detail=f"Agent failed to generate itinerary: {e}")
    except Exception as e:
        logger.error("Unexpected agent error for trip %d: %s", trip_id, str(e))
        raise HTTPException(status_code=500, detail="AI itinerary generation failed unexpectedly")
