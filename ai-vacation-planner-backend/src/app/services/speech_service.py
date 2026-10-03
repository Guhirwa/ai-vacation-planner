"""
speech_service.py

Handles speech-to-text transcription and trip detail extraction from voice input.

Transcription uses faster-whisper running locally with no API key required.
Trip detail extraction uses Claude to parse the transcript into structured
trip fields. Both operations are independent, a failed extraction does not
block the transcript from being returned.
"""

import json
import logging
import tempfile
import os
from faster_whisper import WhisperModel
from anthropic import AsyncAnthropic
from fastapi import HTTPException

from app.config import settings
from app.schemas.voice import TripDetailsFromVoice

logger = logging.getLogger(__name__)

_anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

# Load the Whisper model once at module level to avoid reloading on every request
_whisper_model = WhisperModel(
    settings.whisper_model_size,
    device=settings.whisper_device,
    compute_type=settings.whisper_compute_type,
)


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Transcribe an audio file to text using a local Whisper model.

    Writes the audio bytes to a temporary file, runs Whisper inference,
    and concatenates all segments into a single transcript string.
    The temporary file is deleted after transcription regardless of outcome.

    Args:
        audio_bytes: The raw audio file content.
        filename: The original filename including extension, used to
                  determine the file suffix for the temporary file.

    Returns:
        The transcribed text as a plain string.

    Raises:
        HTTPException(500): If transcription fails for any reason.
    """
    suffix = os.path.splitext(filename)[-1] or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, _ = _whisper_model.transcribe(tmp_path, beam_size=5)
        transcript = " ".join(segment.text.strip() for segment in segments)
        return transcript.strip()
    except Exception as e:
        logger.error("Transcription failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Transcription failed")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def extract_trip_details(transcript: str) -> TripDetailsFromVoice | None:
    """Extract structured trip details from a voice transcript using Claude.

    Sends the transcript to Claude with a structured extraction prompt and
    parses the response into a TripDetailsFromVoice object. Returns None
    if extraction fails rather than raising, so the caller can still return
    the raw transcript even when structured extraction is not possible.

    Args:
        transcript: The raw text transcript from speech-to-text.

    Returns:
        A TripDetailsFromVoice instance if extraction succeeds, None otherwise.
    """
    prompt = f"""Extract trip planning details from this voice transcript and return ONLY a JSON object with no extra text:

Transcript: "{transcript}"

Return this exact JSON structure:
{{
  "destination": "city name",
  "days": number,
  "budget": number in USD,
  "trip_style": "one of: budget, comfort, luxury, family, adventure, romantic, business"
}}

If any field cannot be determined from the transcript use these defaults:
- days: 3
- budget: 1000
- trip_style: "comfort"
- destination: extract whatever location is mentioned"""

    try:
        response = await _anthropic_client.messages.create(
            model=settings.agent_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            raw = "\n".join(inner).strip()
        parsed = json.loads(raw)
        return TripDetailsFromVoice(**parsed, raw_transcript=transcript)
    except Exception as e:
        logger.warning("Trip detail extraction failed: %s", str(e))
        return None
