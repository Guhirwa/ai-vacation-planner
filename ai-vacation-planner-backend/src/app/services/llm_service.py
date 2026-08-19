"""LLM-backed itinerary generation service.

Uses the Anthropic Claude API (model: claude-haiku-4-5) to turn a set of
trip details into a day-by-day travel itinerary. Generation follows a
two-prompt architecture: a fixed SYSTEM_PROMPT establishes the assistant's
role and global constraints (realism, geographic accuracy, budget rules,
JSON-only output), while a per-request user prompt (built by
_build_user_prompt) supplies the specific trip details. The raw model
response is stripped of markdown formatting, parsed as JSON, and validated
against LLMItineraryOutput before being returned to the caller.
"""

import json
import logging
from anthropic import AsyncAnthropic, APIConnectionError, APIStatusError
from fastapi import HTTPException
from pydantic import ValidationError
from app.config import settings
from app.schemas.itinerary import LLMItineraryOutput
from app.services.weather_service import get_weather_summary

logger = logging.getLogger(__name__)

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You are an expert travel planner with deep knowledge of destinations worldwide.

Guidelines you must follow for every response:
- Recommend only real, existing places, attractions, restaurants, and activities.
- All recommendations must be geographically accurate — only suggest places physically located in or immediately around the specified destination.
- Respect the budget strictly:
    * budget style: affordable/free attractions, cheap local street food, public transport only
    * comfort style: mid-range attractions, sit-down restaurants, occasional taxis
    * luxury style: premium experiences, fine dining, private transport
- Structure every response as valid JSON only — no extra text, no markdown, no explanation outside the JSON.
- Never include fictional places, generic placeholders, or activities outside the destination area."""

_STYLE_DESCRIPTIONS = {
    "budget": "low-cost and free attractions, local street food, public transport",
    "comfort": "mid-range attractions, sit-down restaurants, occasional taxis",
    "luxury": "premium experiences, fine dining, private transport",
    "family": "family-friendly attractions, casual dining, easy transport options",
    "adventure": "outdoor adventures, active experiences, local casual dining",
    "romantic": "scenic spots, intimate dining, comfortable private transport",
    "business": "work-focused travel, business hotels, professional dining, convenient transport",
}


def _build_user_prompt(
    destination: str,
    days: int,
    budget: float,
    trip_style: str,
    weather_summary: str | None = None,
) -> str:
    """Build the user-facing prompt sent to the LLM for itinerary generation.

    Args:
        destination: The travel destination (e.g. "Paris").
        days: Number of days the trip lasts.
        budget: Total trip budget in USD.
        trip_style: One of the allowed trip styles (e.g. "budget", "comfort").
        weather_summary: An optional plain-English weather forecast summary.
            When provided, it is added as a prompt section so the LLM can
            favor weather-appropriate activities. Omitted entirely if None.

    Returns:
        A formatted prompt string instructing the LLM to respond with a JSON
        object matching the expected itinerary structure.
    """
    style_desc = _STYLE_DESCRIPTIONS.get(trip_style.lower(), trip_style)
    weather_section = (
        f"\nWeather forecast:\n- {weather_summary}\n" if weather_summary else ""
    )
    return f"""Plan a {days}-day trip to {destination}.

Trip details:
- Total budget: ${budget:,.2f} USD — every suggestion must fit within this budget
- Travel style: {trip_style} ({style_desc})
- Days: exactly {days} days, each with between 3 and 5 activities
{weather_section}
Requirements for each day:
- Include a mix of sightseeing, food experiences, and local culture
- Do not repeat the same activity across different days
- All activities must be real places that physically exist in or immediately around {destination}
- If a weather forecast is provided above, favor outdoor activities on sunny days and indoor/covered activities on rainy days

Respond with ONLY a JSON object in this exact format — no extra text before or after:
{{
  "days": [
    {{
      "day": 1,
      "activities": ["Visit the Eiffel Tower", "Lunch at a local brasserie", "Walk along the Seine River", "Visit Notre Dame Cathedral"]
    }}
  ]
}}"""


async def _call_llm_with_retry(
    destination: str,
    days: int,
    budget: float,
    trip_style: str,
    weather_summary: str | None = None,
) -> LLMItineraryOutput:
    """Attempt to generate a structured itinerary from the LLM, retrying on
    recoverable parsing and validation failures up to settings.llm_max_retries times.

    Args:
        destination: The travel destination.
        days: Number of days the trip lasts.
        budget: Total trip budget in USD.
        trip_style: One of the allowed trip styles.
        weather_summary: An optional plain-English weather forecast summary
            to include in the prompt sent to the LLM.

    Returns:
        A validated LLMItineraryOutput instance.

    Raises:
        HTTPException(500): If all retry attempts are exhausted or a
            non-recoverable API error occurs.
    """
    last_error: Exception | None = None
    user_prompt = _build_user_prompt(destination, days, budget, trip_style, weather_summary)
    logger.debug("LLM user prompt for %s:\n%s", destination, user_prompt)

    for attempt in range(1, settings.llm_max_retries + 1):
        try:
            response = await _client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except APIStatusError:
            raise HTTPException(status_code=500, detail="AI itinerary generation is temporarily unavailable")
        except APIConnectionError:
            raise HTTPException(status_code=500, detail="Could not reach the AI itinerary generation service")
        except Exception:
            raise HTTPException(status_code=500, detail="AI itinerary generation failed unexpectedly")

        raw = response.content[0].text.strip()

        # Strip accidental markdown code fences (```json ... ``` or ``` ... ```)
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            raw = "\n".join(inner).strip()

        try:
            parsed = json.loads(raw)
            return LLMItineraryOutput(**parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning(
                "LLM itinerary generation attempt %d/%d failed: %s",
                attempt,
                settings.llm_max_retries,
                e,
            )

    raise HTTPException(
        status_code=500,
        detail=f"AI itinerary generation failed after {settings.llm_max_retries} attempts: {last_error}",
    )


async def generate_itinerary(
    destination: str,
    days: int,
    budget: float,
    trip_style: str,
) -> LLMItineraryOutput:
    """Generate a day-by-day travel itinerary using the Anthropic Claude LLM.

    Public entry point for itinerary generation. Fetches a weather summary
    for the destination (best-effort — a weather failure never blocks
    itinerary generation) and delegates to _call_llm_with_retry, which builds
    the prompt, calls the Claude API, and validates the response, retrying on
    recoverable JSON/validation failures up to settings.llm_max_retries times.

    Args:
        destination: The travel destination (e.g. "Paris").
        days: Number of days the trip lasts.
        budget: Total trip budget in USD.
        trip_style: One of the allowed trip styles (e.g. "budget", "comfort").

    Returns:
        A validated LLMItineraryOutput instance containing the structured itinerary.

    Raises:
        HTTPException(500): If a non-recoverable API error occurs, or if all
            retry attempts are exhausted.
    """
    try:
        weather_summary = await get_weather_summary(destination)
    except HTTPException as e:
        logger.warning("Weather lookup failed for '%s', continuing without weather context: %s", destination, e.detail)
        weather_summary = None

    return await _call_llm_with_retry(destination, days, budget, trip_style, weather_summary)
