"""
voice.py

Pydantic schemas for the voice input and output API.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.trip import TripCreate


class TripDetailsFromVoice(TripCreate):
    """Trip details extracted from a voice transcript.

    Inherits destination, days, budget, and trip_style straight from
    TripCreate, so a voice proposal is checked against the exact same
    rules as a trip the user creates directly, and can't drift out of
    sync with what /trips/ actually accepts.

    This is a preview, not a saved trip. Nothing is written to the
    database when it's returned, the caller is expected to show it to
    the user for review and correction, then submit the confirmed
    values as a normal POST /trips/ request.

    Attributes:
        destination: The travel destination extracted from the transcript.
        days: Number of days extracted from the transcript.
        budget: Budget in USD extracted from the transcript.
        trip_style: Travel style extracted from the transcript.
        fields_defaulted: Names of the fields above that were not actually
            mentioned in the transcript and were filled in with a default
            instead, so the caller can tell a guess from something the
            user actually said.
        raw_transcript: The original transcript before extraction.
    """
    fields_defaulted: list[str] = Field(default_factory=list)
    raw_transcript: str


class TranscribeResponse(BaseModel):
    """Response schema for the POST /voice/transcribe endpoint.

    Attributes:
        transcript: The raw text transcribed from the audio.
        trip_details: Structured trip details extracted from the transcript,
                      or None if extraction failed.
        message: A human-readable status message.
    """
    transcript: str
    trip_details: Optional[TripDetailsFromVoice] = None
    message: str


class AudioResponse(BaseModel):
    """Metadata response for the GET /itineraries/{trip_id}/audio endpoint.

    The actual audio is returned as a streaming audio/mpeg response.
    This schema is used only for error responses and documentation.

    Attributes:
        trip_id: The ID of the trip the audio was generated for.
        message: A human-readable status message.
    """
    trip_id: int
    message: str
