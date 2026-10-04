"""
voice.py

Pydantic schemas for the voice input and output API.
"""

from pydantic import BaseModel
from typing import Optional


class TripDetailsFromVoice(BaseModel):
    """Trip details extracted from a voice transcript.

    Attributes:
        destination: The travel destination extracted from the transcript.
        days: Number of days extracted from the transcript.
        budget: Budget in USD extracted from the transcript.
        trip_style: Travel style extracted from the transcript.
        raw_transcript: The original transcript before extraction.
    """
    destination: str
    days: int
    budget: float
    trip_style: str
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
