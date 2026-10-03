"""
voice.py

Router for voice input and output endpoints.
Handles audio file uploads for transcription and trip detail extraction.
"""

import logging
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.speech_service import transcribe_audio, extract_trip_details
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
