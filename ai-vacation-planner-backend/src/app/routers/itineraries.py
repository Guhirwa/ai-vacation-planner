"""Itinerary routes for the AI Vacation Planner API.

Exposes endpoints to create an itinerary for a trip (either manually
supplied or AI-generated via the LLM service) and to retrieve an existing
itinerary by trip ID. All routes require an authenticated user and enforce
trip ownership.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_database
from app.models.itinerary import Itinerary
from app.models.trip import Trip
from app.schemas.itinerary import ItineraryCreate, ItineraryResponse, DayActivity
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.llm_service import generate_itinerary

router = APIRouter(prefix="/itineraries", tags=["Itineraries"])


@router.post("", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_itinerary(
    itinerary: ItineraryCreate,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ItineraryResponse:
    """Create an itinerary for a trip, either manually or via AI generation.

    Verifies the trip exists and belongs to the current user, and that no
    itinerary already exists for it. When `generate_with_ai` is True, calls
    the LLM service to generate the day-by-day plan (already validated as an
    LLMItineraryOutput); otherwise uses the manually supplied `days`.
    Persists the result and returns it.

    Args:
        itinerary: The itinerary creation payload (trip_id, generate_with_ai,
            and optionally a manual `days` list).
        database: The database session dependency.
        current_user: The authenticated user, injected via dependency.

    Returns:
        The created itinerary as an ItineraryResponse.

    Raises:
        HTTPException(404): If the trip does not exist.
        HTTPException(403): If the trip does not belong to the current user.
        HTTPException(400): If an itinerary already exists for the trip.
        HTTPException(500): If AI generation fails or returns an invalid structure.
    """
    # Step A: fetch trip, then check ownership separately for clean 404 vs 403
    trip = database.query(Trip).filter(Trip.id == itinerary.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to create itinerary for this trip")

    existing = database.query(Itinerary).filter(Itinerary.trip_id == itinerary.trip_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Itinerary already exists for this trip")

    # Step B: build days list from AI or manual input
    if itinerary.generate_with_ai:
        result = await generate_itinerary(
            trip.destination, trip.days, trip.budget, trip.trip_style
        )
        days_list = [DayActivity(day=d.day, activities=d.activities) for d in result.days]
    else:
        days_list = itinerary.days

    # Step C: persist and return
    database_itinerary = Itinerary(
        trip_id=itinerary.trip_id,
        days_data=[day.model_dump() for day in days_list],
    )
    database.add(database_itinerary)
    database.commit()
    database.refresh(database_itinerary)

    return ItineraryResponse(
        trip_id=itinerary.trip_id,
        itinerary=days_list,
        created_at=database_itinerary.created_at,
        updated_at=database_itinerary.updated_at,
    )


@router.get("/{trip_id}", response_model=ItineraryResponse)
def get_itinerary(
    trip_id: int,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ItineraryResponse:
    """Retrieve the itinerary for a given trip.

    Args:
        trip_id: The ID of the trip whose itinerary should be retrieved.
        database: The database session dependency.
        current_user: The authenticated user, injected via dependency.

    Returns:
        The trip's itinerary as an ItineraryResponse.

    Raises:
        HTTPException(404): If the trip does not belong to the current user,
            or if no itinerary exists for it.
    """
    trip = database.query(Trip).filter(Trip.id == trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    itinerary = database.query(Itinerary).filter(Itinerary.trip_id == trip_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    return ItineraryResponse(
        trip_id=trip_id,
        itinerary=[DayActivity(**day) for day in itinerary.days_data],
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
    )
