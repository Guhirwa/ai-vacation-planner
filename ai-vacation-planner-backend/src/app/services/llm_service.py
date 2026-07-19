import json
from anthropic import AsyncAnthropic
from fastapi import HTTPException
from app.config import settings

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
}


def _build_user_prompt(destination: str, days: int, budget: float, trip_style: str) -> str:
    style_desc = _STYLE_DESCRIPTIONS.get(trip_style.lower(), trip_style)
    return f"""Plan a {days}-day trip to {destination}.

Trip details:
- Total budget: ${budget:,.2f} USD — every suggestion must fit within this budget
- Travel style: {trip_style} ({style_desc})
- Days: exactly {days} days, each with between 3 and 5 activities

Requirements for each day:
- Include a mix of sightseeing, food experiences, and local culture
- Do not repeat the same activity across different days
- All activities must be real places that physically exist in or immediately around {destination}

Respond with ONLY a JSON object in this exact format — no extra text before or after:
{{
  "days": [
    {{
      "day": 1,
      "activities": ["Visit the Eiffel Tower", "Lunch at a local brasserie", "Walk along the Seine River", "Visit Notre Dame Cathedral"]
    }}
  ]
}}"""


async def generate_itinerary(destination: str, days: int, budget: float, trip_style: str) -> list[dict]:
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(destination, days, budget, trip_style)}],
    )

    raw = response.content[0].text.strip()

    # Strip accidental markdown code fences (```json ... ``` or ``` ... ```)
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        raw = "\n".join(inner).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON format")

    if "days" not in parsed:
        raise HTTPException(status_code=500, detail="LLM response missing required itinerary structure")

    return parsed["days"]


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(generate_itinerary("Paris", 2, 1500, "budget"))
    print(result)
