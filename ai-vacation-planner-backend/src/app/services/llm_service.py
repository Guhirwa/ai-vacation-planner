import json
from anthropic import AsyncAnthropic
from app.config import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-sonnet-4-6"


async def generate_itinerary(destination: str, days: int, budget: float, trip_style: str) -> list[dict]:
    prompt = (
        f"Generate a detailed {days}-day travel itinerary for {destination}.\n"
        f"Budget: ${budget}\n"
        f"Trip style: {trip_style}\n\n"
        "Return ONLY a valid JSON array with no extra text, no markdown, no code fences.\n"
        f"The array must have exactly {days} elements. Each element must have:\n"
        '- "day": integer (1 through ' + str(days) + ")\n"
        '- "activities": array of 3 to 5 strings describing activities for that day\n\n'
        "Example:\n"
        '[{"day": 1, "activities": ["Visit Eiffel Tower", "Seine River cruise", "Dinner in Montmartre"]}]'
    )

    response = await _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if the model wraps its output
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    return json.loads(raw)
