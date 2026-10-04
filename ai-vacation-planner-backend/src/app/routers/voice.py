"""
voice.py

Router for voice input and output endpoints.
Handles audio file uploads for transcription and trip detail extraction.
"""

import logging
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.itinerary import Itinerary
from app.models.trip import Trip
from app.database import get_database
from sqlalchemy.orm import Session
from app.services.speech_service import (
    transcribe_audio,
    extract_trip_details,
    synthesize_speech,
    summarize_itinerary_for_speech,
)
from app.schemas.voice import TranscribeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post("/transcribe", response_model=TranscribeResponse, status_code=200)
async def transcribe_voice(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    """Transcribe an uploaded audio file and extract trip details from it.

    Accepts an audio file (mp3, wav, m4a, webm), transcribes it using
    a local Whisper model, then attempts to extract structured trip details
    using Claude. The transcript is always returned even if extraction fails.

    Args:
        file: The uploaded audio file.
        current_user: The authenticated user making the request.

    Returns:
        A TranscribeResponse containing the transcript and optionally
        extracted trip details.

    Raises:
        HTTPException(400): If the uploaded file type is not supported.
        HTTPException(500): If transcription fails.
    """
    allowed_types = {
        "audio/mpeg", "audio/wav", "audio/mp4",
        "audio/webm", "audio/x-m4a", "audio/ogg"
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Supported formats: mp3, wav, m4a, webm, ogg"
        )

    audio_bytes = await file.read()
    transcript = await transcribe_audio(audio_bytes, file.filename)
    trip_details = await extract_trip_details(transcript)

    return TranscribeResponse(
        transcript=transcript,
        trip_details=trip_details,
        message="Transcription successful",
    )


@router.get("/itineraries/{trip_id}/audio")
async def get_itinerary_audio(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database),
) -> StreamingResponse:
    """Convert a saved itinerary to speech and return it as an audio file.

    Fetches the itinerary for the given trip, uses Claude to summarize it
    into natural spoken language, then converts the summary to MP3 audio
    using gTTS. Returns the audio as a streaming response the client can
    play directly.

    Args:
        trip_id: The ID of the trip whose itinerary to convert to audio.
        current_user: The authenticated user making the request.
        db: The database session.

    Returns:
        A StreamingResponse containing the MP3 audio file.

    Raises:
        HTTPException(404): If the trip or itinerary does not exist.
        HTTPException(403): If the trip does not belong to the current user.
        HTTPException(500): If speech synthesis fails.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this trip")

    itinerary = db.query(Itinerary).filter(Itinerary.trip_id == trip_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="No itinerary found for this trip")

    summary = await summarize_itinerary_for_speech(itinerary.days_data)
    audio_bytes = await synthesize_speech(summary)

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"attachment; filename=itinerary_{trip_id}.mp3"},
    )
