"""
speech_service.py

Handles speech-to-text transcription and trip detail extraction from voice input.

Transcription uses faster-whisper running locally with no API key required.
Trip detail extraction uses Claude to parse the transcript into structured
trip fields. Both operations are independent, a failed extraction does not
block the transcript from being returned.
"""

import asyncio
import io
import json
import logging
import tempfile
import threading
import os
from faster_whisper import WhisperModel
from gtts import gTTS
from anthropic import AsyncAnthropic
from fastapi import HTTPException

from app.config import settings
from app.schemas.voice import TripDetailsFromVoice
from app.observability import log_llm_call

logger = logging.getLogger(__name__)

_anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

# Used to fill in trip details the transcript doesn't actually mention.
# Applied here rather than left to the model, so we always know which
# fields were a real guess versus something the user said.
DEFAULT_TRIP_DAYS = 3
DEFAULT_TRIP_BUDGET = 1000.0
DEFAULT_TRIP_STYLE = "comfort"

# Loaded lazily on first use instead of at import time, so a failure to
# load it only affects transcription requests instead of preventing the
# whole API from starting.
_whisper_model: WhisperModel | None = None
_whisper_model_lock = threading.Lock()


def _get_whisper_model() -> WhisperModel:
    """Load the Whisper model on first use and cache it for later calls.

    Guarded by a lock so two transcription requests arriving at the same
    time can't both end up loading the model at once.

    Returns:
        The loaded WhisperModel instance.

    Raises:
        HTTPException(503): If the model fails to load.
    """
    global _whisper_model
    if _whisper_model is None:
        with _whisper_model_lock:
            if _whisper_model is None:
                try:
                    _whisper_model = WhisperModel(
                        settings.whisper_model_size,
                        device=settings.whisper_device,
                        compute_type=settings.whisper_compute_type,
                    )
                except Exception as e:
                    logger.error("Failed to load Whisper model: %s", str(e))
                    raise HTTPException(
                        status_code=503,
                        detail="Speech-to-text is currently unavailable",
                    )
    return _whisper_model


def _run_whisper_transcription(tmp_path: str) -> str:
    """Run Whisper inference and build the full transcript string.

    This does all of faster-whisper's actual work, including loading the
    model on first use and iterating its segment generator, which is
    where the blocking CPU work actually happens rather than in the
    initial transcribe() call. Kept as a plain function so it can be run
    in a worker thread instead of blocking the event loop.

    Args:
        tmp_path: Path to the temporary audio file to transcribe.

    Returns:
        The transcribed text as a plain string.
    """
    model = _get_whisper_model()
    segments, _ = model.transcribe(tmp_path, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Transcribe an audio file to text using a local Whisper model.

    Writes the audio bytes to a temporary file, then runs Whisper
    inference in a worker thread so it doesn't block the event loop
    while other requests are being handled.
    The temporary file is deleted after transcription regardless of outcome.

    Args:
        audio_bytes: The raw audio file content.
        filename: The original filename including extension, used to
                  determine the file suffix for the temporary file.

    Returns:
        The transcribed text as a plain string.

    Raises:
        HTTPException(500): If transcription fails for any reason.
        HTTPException(503): If the Whisper model fails to load.
    """
    suffix = os.path.splitext(filename)[-1] or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        return await asyncio.to_thread(_run_whisper_transcription, tmp_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Transcription failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Transcription failed")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def extract_trip_details(transcript: str) -> TripDetailsFromVoice | None:
    """Extract structured trip details from a voice transcript using Claude.

    Sends the transcript to Claude with a structured extraction prompt and
    parses the response into a TripDetailsFromVoice object. Claude is asked
    to return null for anything the transcript doesn't actually mention,
    rather than inventing a plausible-looking value itself, so this
    function can fill in the real defaults on its own and record which
    fields were genuinely said versus guessed. Returns None if extraction
    fails rather than raising, so the caller can still return the raw
    transcript even when structured extraction is not possible.

    Args:
        transcript: The raw text transcript from speech-to-text.

    Returns:
        A TripDetailsFromVoice instance if extraction succeeds, None otherwise.
    """
    prompt = f"""Extract trip planning details from this voice transcript and return ONLY a JSON object with no extra text:

Transcript: "{transcript}"

Return this exact JSON structure:
{{
  "destination": "city name, or null if not mentioned",
  "days": number, or null if not mentioned,
  "budget": number in USD, or null if not mentioned,
  "trip_style": "one of: budget, comfort, luxury, family, adventure, romantic, business, or null if not mentioned"
}}

Only fill in a field if the transcript actually says it. Use null for
anything not mentioned, do not guess or make up a value yourself."""

    try:
        with log_llm_call("speech.extract_trip_details", settings.agent_model) as usage:
            response = await _anthropic_client.messages.create(
                model=settings.agent_model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            usage["input_tokens"] = response.usage.input_tokens
            usage["output_tokens"] = response.usage.output_tokens
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            raw = "\n".join(inner).strip()
        parsed = json.loads(raw)

        destination = parsed.get("destination")
        if not destination:
            logger.warning("Trip detail extraction found no destination in transcript")
            return None

        fields_defaulted = []

        days = parsed.get("days")
        if days is None:
            days = DEFAULT_TRIP_DAYS
            fields_defaulted.append("days")

        budget = parsed.get("budget")
        if budget is None:
            budget = DEFAULT_TRIP_BUDGET
            fields_defaulted.append("budget")

        trip_style = parsed.get("trip_style")
        if not trip_style:
            trip_style = DEFAULT_TRIP_STYLE
            fields_defaulted.append("trip_style")

        return TripDetailsFromVoice(
            destination=destination,
            days=days,
            budget=budget,
            trip_style=trip_style,
            fields_defaulted=fields_defaulted,
            raw_transcript=transcript,
        )
    except Exception as e:
        logger.warning("Trip detail extraction failed: %s", str(e))
        return None


def _run_text_to_speech(text: str, language: str) -> bytes:
    """Generate MP3 audio bytes from text using gTTS.

    gTTS makes a blocking network call during write_to_fp, so this is kept
    as a plain function to run in a worker thread instead of blocking the
    event loop.

    Args:
        text: The text to convert to speech.
        language: The language code for speech synthesis.

    Returns:
        The generated audio as raw MP3 bytes.
    """
    tts = gTTS(text=text, lang=language, slow=False)
    audio_buffer = io.BytesIO()
    tts.write_to_fp(audio_buffer)
    audio_buffer.seek(0)
    return audio_buffer.read()


async def synthesize_speech(text: str, language: str = "en") -> bytes:
    """Convert text to speech audio using gTTS.

    Generates an MP3 audio file in memory from the provided text using
    Google Text-to-Speech, running the actual conversion in a worker
    thread so it doesn't block the event loop. No API key is required.

    Args:
        text: The text to convert to speech.
        language: The language code for speech synthesis. Defaults to "en".

    Returns:
        The generated audio as raw MP3 bytes.

    Raises:
        HTTPException(500): If speech synthesis fails for any reason.
    """
    try:
        return await asyncio.to_thread(_run_text_to_speech, text, language)
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
        with log_llm_call("speech.summarize_itinerary_for_speech", settings.agent_model) as usage:
            response = await _anthropic_client.messages.create(
                model=settings.agent_model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            usage["input_tokens"] = response.usage.input_tokens
            usage["output_tokens"] = response.usage.output_tokens
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("Itinerary summarization failed, using fallback: %s", str(e))
        return days_text
