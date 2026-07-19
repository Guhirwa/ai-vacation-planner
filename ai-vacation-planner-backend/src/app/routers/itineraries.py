from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
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
):
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
        raw_days = await generate_itinerary(
            trip.destination, trip.days, trip.budget, trip.trip_style
        )
        try:
            days_list = [DayActivity(**d) for d in raw_days]
        except (ValidationError, TypeError):
            raise HTTPException(status_code=500, detail="LLM returned an activity in an unexpected format")
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
):
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
