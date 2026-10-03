"""
speech_service.py

Handles speech-to-text transcription and trip detail extraction from voice input.

Transcription uses faster-whisper running locally with no API key required.
Trip detail extraction uses Claude to parse the transcript into structured
trip fields. Both operations are independent, a failed extraction does not
block the transcript from being returned.
"""

import io
import json
import logging
import tempfile
import os
from faster_whisper import WhisperModel
from gtts import gTTS
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


async def synthesize_speech(text: str, language: str = "en") -> bytes:
    """Convert text to speech audio using gTTS.

    Generates an MP3 audio file in memory from the provided text using
    Google Text-to-Speech. No API key is required.

    Args:
        text: The text to convert to speech.
        language: The language code for speech synthesis. Defaults to "en".

    Returns:
        The generated audio as raw MP3 bytes.

    Raises:
        HTTPException(500): If speech synthesis fails for any reason.
    """
    try:
        tts = gTTS(text=text, lang=language, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer.read()
    except Exception as e:
        logger.error("Speech synthesis failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Speech synthesis failed")


async def summarize_itinerary_for_speech(itinerary_days: list[dict]) -> str:
    """Convert a structured itinerary into natural spoken language.

    Takes the list of itinerary days and activities and uses Claude to
    produce a friendly, conversational summary suitable for text-to-speech
    output. The summary is shorter and more natural than the raw JSON.

    Args:
        itinerary_days: A list of dicts, each with a "day" key and an
                        "activities" key containing a list of strings.

    Returns:
        A plain-text summary of the itinerary suitable for speech output.
    """
    days_text = "\n".join(
        f"Day {d['day']}: {', '.join(d['activities'])}"
        for d in itinerary_days
    )
    prompt = f"""Convert this travel itinerary into a friendly, conversational spoken summary.
Write it as if you are a travel assistant reading the plan aloud to the traveller.
Keep it natural, warm, and concise, no bullet points, no markdown, just flowing sentences.

Itinerary:
{days_text}

Spoken summary:"""

    try:
        response = await _anthropic_client.messages.create(
            model=settings.agent_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("Itinerary summarization failed, using fallback: %s", str(e))
        return days_text
